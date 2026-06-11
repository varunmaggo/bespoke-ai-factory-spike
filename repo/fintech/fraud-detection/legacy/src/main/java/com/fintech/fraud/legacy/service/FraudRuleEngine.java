package com.fintech.fraud.legacy.service;

import com.fintech.fraud.legacy.model.CardTransaction;
import com.fintech.fraud.legacy.model.FraudAssessment;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * LEGACY — Hardcoded if/else fraud rule engine.
 *
 * Problems this class demonstrates (all fixed by the fraud-triage-agent):
 *
 *   1. Magic-number thresholds (10_000, 3, 5_000…) — tuning a rule is a
 *      code change, a release and a deployment
 *   2. Additive uncalibrated score — RULE_HIGH_AMOUNT(50) + RULE_GEO(30)
 *      says nothing about actual fraud probability
 *   3. Rule IDs as the only output — an analyst (or a cardholder dispute)
 *      gets "RULE_VELOCITY" with zero narrative
 *   4. Velocity window state in an in-memory map — resets on deploy and is
 *      invisible to the other instances behind the load balancer
 *   5. No feedback loop — confirmed fraud/false-positive outcomes are never
 *      used to improve detection
 *
 * Target (fintech-rules-to-agentic-rag → kiro/specs/fraud-triage-agent.kiro.yaml):
 *   - vector_search retrieves similar adjudicated cases + typology docs
 *   - Claude reasons over the transaction in context and writes a cited
 *     triage narrative with a calibrated risk band
 *   - eval gate scores narrative faithfulness before the alert is queued
 *   - adjudication outcomes are fed back into the case corpus nightly
 */
@Service
public class FraudRuleEngine {

    private static final Logger log = LoggerFactory.getLogger(FraudRuleEngine.class);

    // PROBLEM: thresholds frozen in code
    private static final double HIGH_AMOUNT_THRESHOLD = 10_000.00;
    private static final double UNUSUAL_MCC_AMOUNT = 5_000.00;
    private static final int VELOCITY_MAX_TXNS = 3;
    private static final long VELOCITY_WINDOW_MS = 60_000;
    private static final int FLAG_SCORE_THRESHOLD = 50;

    private static final List<String> HIGH_RISK_COUNTRIES = List.of("NG", "RU", "VE");
    private static final List<String> UNUSUAL_MCCS = List.of("7995", "6051"); // gambling, crypto

    // PROBLEM: velocity state per JVM — not shared, not persistent
    private final Map<String, Deque<Long>> recentTxnsByCard = new HashMap<>();

    public synchronized FraudAssessment assess(CardTransaction txn) {
        int score = 0;
        List<String> triggered = new ArrayList<>();

        if (txn.getAmount() > HIGH_AMOUNT_THRESHOLD) {
            score += 50;
            triggered.add("RULE_HIGH_AMOUNT");
        }

        if (HIGH_RISK_COUNTRIES.contains(txn.getCountry())) {
            score += 30;
            triggered.add("RULE_HIGH_RISK_GEO");
        }

        if (UNUSUAL_MCCS.contains(txn.getMerchantCategory()) && txn.getAmount() > UNUSUAL_MCC_AMOUNT) {
            score += 40;
            triggered.add("RULE_UNUSUAL_MCC_AMOUNT");
        }

        // Velocity: more than N transactions on one card inside the window
        Deque<Long> window = recentTxnsByCard.computeIfAbsent(txn.getCardId(), k -> new ArrayDeque<>());
        long now = txn.getTimestampEpochMs();
        while (!window.isEmpty() && now - window.peekFirst() > VELOCITY_WINDOW_MS) {
            window.pollFirst();
        }
        window.addLast(now);
        if (window.size() > VELOCITY_MAX_TXNS) {
            score += 35;
            triggered.add("RULE_VELOCITY");
        }

        boolean flagged = score >= FLAG_SCORE_THRESHOLD;
        log.info("Assessed txn card={} score={} flagged={} rules={}",
                txn.getCardId(), score, flagged, triggered);

        return new FraudAssessment(flagged, score, triggered);
    }
}
