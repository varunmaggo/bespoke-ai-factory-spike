#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_local.sh — Run the three-tier DeepEval suite locally
#
# Usage:
#   cd <project-root>
#   ./evals/deepeval/run_local.sh [tier1|tier2|lending|rag|all]
#
# Prerequisites:
#   pip install -r requirements-eval.txt
#
# Tier 3 (LLM judges) requires ANTHROPIC_API_KEY or OPENAI_API_KEY.
# Tiers 1 & 2 run fully offline.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TARGET="${1:-all}"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RESET='\033[0m'

header() { echo -e "\n${BOLD}${CYAN}▶ $1${RESET}"; }
ok()     { echo -e "${GREEN}  ✅ $1${RESET}"; }
warn()   { echo -e "${YELLOW}  ⚠️  $1${RESET}"; }

# Disable DeepEval telemetry during local runs
export DEEPEVAL_TELEMETRY_OPT_OUT=YES

run_lending_tier1() {
    header "Lending Demo — Tier 1 Hard Gates"
    python -m pytest lending_demo/test_tier1_gates.py -v \
        --tb=short \
        --no-header \
        -p no:deepeval \
        && ok "Tier 1 lending: all hard gates passed"
}

run_lending_tier2() {
    header "Lending Demo — Tier 2 Slice Disparity"
    python -m pytest lending_demo/test_tier2_disparity.py -v \
        --tb=short \
        --no-header \
        -p no:deepeval \
        && ok "Tier 2 lending: disparity report complete"
}

run_rag_tier1() {
    header "RAG Pipeline — Tier 1 Hard Gates"
    python -m pytest rag_tiers/test_tier1_gates.py -v \
        --tb=short \
        --no-header \
        -p no:deepeval \
        && ok "Tier 1 RAG: all hard gates passed"
}

run_rag_tier2() {
    header "RAG Pipeline — Tier 2 Slice Disparity"
    python -m pytest rag_tiers/test_tier2_disparity.py -v \
        --tb=short \
        --no-header \
        -p no:deepeval \
        -s \
        && ok "Tier 2 RAG: quality disparity within threshold"
}

run_tier3_warning() {
    warn "Tier 3 (LLM judges, ci_suite.py) requires ANTHROPIC_API_KEY or OPENAI_API_KEY."
    warn "Set the key and run: pytest ci_suite.py -v"
}

case "$TARGET" in
    tier1)
        run_lending_tier1
        run_rag_tier1
        ;;
    tier2)
        run_lending_tier2
        run_rag_tier2
        ;;
    lending)
        run_lending_tier1
        run_lending_tier2
        ;;
    rag)
        run_rag_tier1
        run_rag_tier2
        ;;
    all)
        run_lending_tier1
        run_lending_tier2
        run_rag_tier1
        run_rag_tier2
        run_tier3_warning
        ;;
    *)
        echo "Usage: $0 [tier1|tier2|lending|rag|all]"
        exit 1
        ;;
esac
