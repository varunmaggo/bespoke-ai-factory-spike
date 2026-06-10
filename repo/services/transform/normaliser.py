"""
services/transform/normaliser.py — local implementation of the
"enterprise-context-normaliser" AWS Transform Custom definition.

Mirrors transformation_definitions/enterprise-context-normaliser/transformation_definition.md:
  1. PII redaction
  2. Date normalisation -> ISO-8601
  3. SAP OData payload flattening
  4. Context window truncation (cl100k_base token budget)

Used as a fallback when the `atx` CLI is not available (e.g. local dev, CI).
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

import tiktoken

VERSION = "1.2.0"

PII_FIELD_NAMES = {
    "ssn", "social_security_number", "national_id",
    "credit_card", "card_number", "cvv", "card_expiry",
    "password", "hashed_password", "api_key", "secret", "token",
    "access_token", "refresh_token",
    "dob", "date_of_birth", "birth_date",
    "phone", "phone_number", "mobile", "fax",
    "email", "email_address",
}

_ENCODING = tiktoken.get_encoding("cl100k_base")

_MONTH_NAMES = "|".join([
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
])

_ISO_DATE_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")
_SLASH_RE      = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_YYYYMMDD_RE   = re.compile(r"^\d{8}$")
_DOT_RE        = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")
_DMON_RE       = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$")
_MONTHNAME_RE  = re.compile(rf"^(?:{_MONTH_NAMES})\s+\d{{1,2}},\s*\d{{4}}$")
_UNIX_RE       = re.compile(r"^\d{10}$")
_DATE_LIKE_RE  = re.compile(r"^\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}$")

_PASCAL_RE = re.compile(r"(?<!^)(?=[A-Z])")


# ── Date normalisation ────────────────────────────────────────────────────────

def _try_parse_date(value: str) -> str | None:
    """Try to parse `value` as a recognised date format and return ISO-8601, or None."""
    if _SLASH_RE.match(value):
        a, b, year_s = value.split("/")
        a, b, year = int(a), int(b), int(year_s)
        if a > 12:
            day, month = a, b
        elif b > 12:
            month, day = a, b
        else:
            day, month = a, b  # ambiguous — default to DD/MM/YYYY
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    if _YYYYMMDD_RE.match(value):
        try:
            return datetime(int(value[:4]), int(value[4:6]), int(value[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            return None

    if _DOT_RE.match(value):
        day_s, month_s, year_s = value.split(".")
        try:
            return datetime(int(year_s), int(month_s), int(day_s)).strftime("%Y-%m-%d")
        except ValueError:
            return None

    if _DMON_RE.match(value):
        try:
            return datetime.strptime(value, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None

    if _MONTHNAME_RE.match(value):
        try:
            return datetime.strptime(value, "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            return None

    if _UNIX_RE.match(value):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError, OSError):
            return None

    return None


def _looks_like_date(value: str) -> bool:
    return bool(_DATE_LIKE_RE.match(value) or _DMON_RE.match(value) or _MONTHNAME_RE.match(value))


# ── PII redaction + date normalisation (single recursive pass) ───────────────

def _walk(obj, path: list[str], redacted: list[str], date_count: list[int], date_failures: list[str]):
    if isinstance(obj, dict):
        return {
            k: _walk_value(k, v, path + [str(k)], redacted, date_count, date_failures)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_walk(v, path, redacted, date_count, date_failures) for v in obj]
    return obj


def _walk_value(key, value, path: list[str], redacted: list[str], date_count: list[int], date_failures: list[str]):
    if isinstance(value, str):
        if key.lower() in PII_FIELD_NAMES:
            redacted.append(".".join(path))
            return "[REDACTED]"
        if _ISO_DATE_RE.match(value):
            return value
        parsed = _try_parse_date(value)
        if parsed is not None:
            date_count[0] += 1
            return parsed
        if _looks_like_date(value):
            date_failures.append(".".join(path))
        return value
    if isinstance(value, (dict, list)):
        return _walk(value, path, redacted, date_count, date_failures)
    return value


# ── SAP payload flattening ────────────────────────────────────────────────────

def _to_snake_case(name: str) -> str:
    return _PASCAL_RE.sub("_", name).lower()


def _flatten_item(item: dict, prefix: str = "") -> dict:
    flat: dict = {}
    for k, v in item.items():
        if k.startswith("__") or k.startswith("@odata"):
            continue
        snake_key = _to_snake_case(k)
        full_key = f"{prefix}_{snake_key}" if prefix else snake_key
        if isinstance(v, dict):
            flat.update(_flatten_item(v, full_key))
        else:
            flat[full_key] = v
    return flat


def _flatten_sap(payload):
    """If `payload` is `{"d": {"results": [...]}}`, return (flattened_list, True)."""
    if not isinstance(payload, dict):
        return payload, False
    d = payload.get("d")
    if not isinstance(d, dict):
        return payload, False
    results = d.get("results")
    if not isinstance(results, list):
        return payload, False
    flattened = [_flatten_item(item) if isinstance(item, dict) else item for item in results]
    return flattened, True


# ── Context window truncation ─────────────────────────────────────────────────

def _token_count(chunk) -> int:
    text = chunk.get("content") if isinstance(chunk, dict) else None
    if text is None:
        text = json.dumps(chunk, default=str)
    return len(_ENCODING.encode(str(text)))


def _truncate(chunks: list, max_tokens: int) -> tuple[list, bool, int]:
    counts = [_token_count(c) for c in chunks]
    total = sum(counts)
    if total <= max_tokens:
        return chunks, False, 0

    has_score = any(isinstance(c, dict) and ("score" in c or "relevance_score" in c) for c in chunks)
    if has_score:
        order = sorted(
            range(len(chunks)),
            key=lambda i: chunks[i].get("score", chunks[i].get("relevance_score", 0)) if isinstance(chunks[i], dict) else 0,
            reverse=True,
        )
    else:
        order = list(range(len(chunks)))

    kept = set(order)
    dropped = 0
    for i in reversed(order):
        if total <= max_tokens:
            break
        kept.discard(i)
        total -= counts[i]
        dropped += 1

    result = [chunks[i] for i in range(len(chunks)) if i in kept]
    return result, dropped > 0, dropped


# ── Entry point ────────────────────────────────────────────────────────────────

def normalise(payload: dict, max_tokens: int = 80_000) -> dict:
    """Apply the enterprise-context-normaliser transformation to `payload`."""
    payload = copy.deepcopy(payload)

    redacted: list[str] = []
    date_count = [0]
    date_failures: list[str] = []

    payload = _walk(payload, [], redacted, date_count, date_failures)

    sap_flattened = False
    if isinstance(payload, dict):
        if isinstance(payload.get("chunks"), list):
            new_chunks = []
            for chunk in payload["chunks"]:
                flat, did_flatten = _flatten_sap(chunk)
                if did_flatten:
                    sap_flattened = True
                    new_chunks.extend(flat)
                else:
                    new_chunks.append(chunk)
            payload["chunks"] = new_chunks
        else:
            flat, did_flatten = _flatten_sap(payload)
            if did_flatten:
                sap_flattened = True
                payload = {"chunks": flat}

    truncated = False
    chunks_dropped = 0
    original_chunk_count = 0
    if isinstance(payload.get("chunks"), list):
        chunks = payload["chunks"]
        original_chunk_count = len(chunks)
        chunks, truncated, chunks_dropped = _truncate(chunks, max_tokens)
        payload["chunks"] = chunks

    payload["_transform_metadata"] = {
        "version": VERSION,
        "applied_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pii_redacted": redacted,
        "dates_normalised": date_count[0],
        "date_parse_failures": date_failures,
        "sap_flattened": sap_flattened,
        "truncated": truncated,
        "chunks_dropped": chunks_dropped,
        "original_chunk_count": original_chunk_count,
    }
    return payload
