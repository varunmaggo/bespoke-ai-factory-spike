package com.fintech.fx.legacy.service;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class FxConversionServiceTest {

    private final FxConversionService service = new FxConversionService();

    @BeforeEach
    void seedRates() {
        // Tests must mutate the global static cache — itself a smell the
        // modern immutable-snapshot design removes
        FxRateCache.RATES.put("GBPUSD", 1.27);
        FxRateCache.RATES.put("USDJPY", 155.0);
        FxRateCache.RATES.put("EURGBP", 0.8567);
    }

    @AfterEach
    void clearRates() {
        FxRateCache.RATES.clear();
    }

    @Test
    void directRateConversion() {
        assertEquals(127.0, service.convert("GBP", "USD", 100.0), 0.0001);
    }

    @Test
    void inverseRateConversion() {
        assertEquals(100.0 / 1.27, service.convert("USD", "GBP", 100.0), 0.0001);
    }

    @Test
    void crossRateViaUsd() {
        assertEquals(100.0 * 1.27 * 155.0, service.convert("GBP", "JPY", 100.0), 0.0001);
    }

    @Test
    void doubleArithmeticDriftIsObservable() {
        // DOCUMENTED GAP: converting out and back does not round-trip in
        // double arithmetic; the modern BigDecimal implementation defines
        // explicit precision and rounding policy per currency pair
        double out = service.convert("EUR", "GBP", 19.99);   // 19.99 * 0.8567
        double back = service.convert("GBP", "EUR", out);    // ... / 0.8567 (inverse path)
        assertNotEquals(19.99, back);                         // 19.989999999999995
        assertEquals(19.99, back, 1e-12);
    }

    @Test
    void unknownPairThrowsGenericException() {
        assertThrows(IllegalArgumentException.class,
                () -> service.convert("GBP", "CHF", 100.0));
    }
}
