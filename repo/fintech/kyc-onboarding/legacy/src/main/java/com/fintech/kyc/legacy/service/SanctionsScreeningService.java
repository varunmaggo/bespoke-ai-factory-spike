package com.fintech.kyc.legacy.service;

import com.fintech.kyc.legacy.model.CustomerApplication;
import com.fintech.kyc.legacy.model.ScreeningResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * LEGACY — Exact-match sanctions screening.
 *
 * Problems this class demonstrates (all fixed by the kyc-screening-agent):
 *
 *   1. Watchlist hardcoded in the binary — every OFAC/HMT list update is a
 *      release; lists actually change weekly
 *   2. Exact uppercase string match — "JON DOE" passes while "JOHN DOE" is
 *      listed; transliterations (Cyrillic→Latin), aliases and middle names
 *      all slip through
 *   3. Naive substring check causes false positives on common surnames —
 *      analysts drown in noise and start rubber-stamping
 *   4. No risk narrative, no evidence citations, no audit trail
 *
 * Target (fintech-rules-to-agentic-rag → kiro/specs/kyc-screening-agent.kiro.yaml):
 *   - vector_search over the sanctions corpus (semantic + fuzzy match)
 *   - graph_query entity resolution (aliases, associates, ownership chains)
 *   - aws_transform PII redaction before any LLM call
 *   - Claude generates a cited risk narrative; eval gate scores faithfulness
 *     before the case reaches an analyst
 */
@Service
public class SanctionsScreeningService {

    private static final Logger log = LoggerFactory.getLogger(SanctionsScreeningService.class);

    // PROBLEM: the "list" — frozen at build time, uppercase-exact entries
    private static final List<String> WATCHLIST = List.of(
            "JOHN DOE",
            "ACME SHELL HOLDINGS",
            "IVAN PETROV",
            "GLOBAL TRADE FZE"
    );

    private static final List<String> HIGH_RISK_COUNTRIES = List.of("KP", "IR", "SY");

    public ScreeningResult screen(CustomerApplication application) {
        String name = application.getFullName().toUpperCase(Locale.ROOT).trim();
        List<String> matches = new ArrayList<>();

        for (String listed : WATCHLIST) {
            // PROBLEM: contains() — "IVANOVA PETROVA" false-positives on
            // "IVAN PETROV"-adjacent substrings, while "I. Petrov" passes
            if (name.contains(listed) || listed.contains(name)) {
                matches.add(listed);
            }
        }

        boolean highRiskCountry = HIGH_RISK_COUNTRIES.contains(application.getNationality())
                || HIGH_RISK_COUNTRIES.contains(application.getResidencyCountry());

        boolean blocked = !matches.isEmpty() || highRiskCountry;
        log.info("Screened applicant name='{}' blocked={} matches={}", name, blocked, matches.size());

        // PROBLEM: the analyst sees BLOCK + a name — no similarity score,
        // no source document, no reasoning to review or appeal
        return new ScreeningResult(blocked, matches);
    }
}
