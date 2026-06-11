package com.fintech.fraud.legacy.service;

import com.fintech.fraud.legacy.model.CardTransaction;
import com.fintech.fraud.legacy.model.FraudAssessment;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FraudRuleEngineTest {

    private final FraudRuleEngine engine = new FraudRuleEngine();

    @Test
    void normalTransactionPasses() {
        FraudAssessment a = engine.assess(
                new CardTransaction("card-1", 42.50, "5411", "GB", 1_000_000L));
        assertFalse(a.isFlagged());
        assertEquals(0, a.getScore());
    }

    @Test
    void highAmountIsFlagged() {
        FraudAssessment a = engine.assess(
                new CardTransaction("card-2", 15_000.00, "5411", "GB", 1_000_000L));
        assertTrue(a.isFlagged());
        assertTrue(a.getTriggeredRules().contains("RULE_HIGH_AMOUNT"));
    }

    @Test
    void velocityBurstIsFlagged() {
        long base = 1_000_000L;
        for (int i = 0; i < 3; i++) {
            engine.assess(new CardTransaction("card-3", 20.00, "5411", "GB", base + i * 1000L));
        }
        FraudAssessment fourth = engine.assess(
                new CardTransaction("card-3", 20.00, "5411", "GB", base + 4000L));

        assertTrue(fourth.getTriggeredRules().contains("RULE_VELOCITY"));
        // DOCUMENTED GAP: velocity alone (35) doesn't reach the flag
        // threshold (50) — uncalibrated additive scoring in action
        assertFalse(fourth.isFlagged());
    }

    @Test
    void geoRuleAloneDoesNotFlag_noRiskNarrativeEither() {
        FraudAssessment a = engine.assess(
                new CardTransaction("card-4", 100.00, "5411", "RU", 1_000_000L));
        assertFalse(a.isFlagged());
        // The only "explanation" the legacy engine can ever give:
        assertEquals(1, a.getTriggeredRules().size());
        assertEquals("RULE_HIGH_RISK_GEO", a.getTriggeredRules().get(0));
    }
}
