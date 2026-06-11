package com.fintech.kyc.legacy.service;

import com.fintech.kyc.legacy.model.CustomerApplication;
import com.fintech.kyc.legacy.model.ScreeningResult;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SanctionsScreeningServiceTest {

    private final SanctionsScreeningService service = new SanctionsScreeningService();

    @Test
    void exactWatchlistMatchIsBlocked() {
        ScreeningResult result = service.screen(
                new CustomerApplication("John Doe", "1980-01-01", "GB", "GB"));
        assertTrue(result.isBlocked());
    }

    @Test
    void highRiskCountryIsBlocked() {
        ScreeningResult result = service.screen(
                new CustomerApplication("Jane Smith", "1990-05-05", "KP", "KP"));
        assertTrue(result.isBlocked());
    }

    @Test
    void trivialSpellingVariantSlipsThrough() {
        // DOCUMENTED GAP: "Jon Doe" is the listed "John Doe" minus one letter,
        // yet exact matching lets it through. The kyc-screening-agent's
        // semantic search + graph alias resolution catches this — see
        // kiro/specs/kyc-screening-agent.kiro.yaml.
        ScreeningResult result = service.screen(
                new CustomerApplication("Jon Doe", "1980-01-01", "GB", "GB"));
        assertFalse(result.isBlocked(), "legacy screening now catches variants — update the demo narrative");
    }

    @Test
    void transliteratedAliasSlipsThrough() {
        // DOCUMENTED GAP: same person as "IVAN PETROV", different transliteration
        ScreeningResult result = service.screen(
                new CustomerApplication("Iwan Petroff", "1975-03-03", "GB", "GB"));
        assertFalse(result.isBlocked(), "legacy screening now catches transliterations — update the demo narrative");
    }
}
