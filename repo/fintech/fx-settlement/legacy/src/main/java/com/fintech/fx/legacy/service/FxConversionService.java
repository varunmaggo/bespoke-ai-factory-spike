package com.fintech.fx.legacy.service;

import org.springframework.stereotype.Service;

/**
 * LEGACY — FX conversion over the static cache.
 *
 * Problems this class demonstrates:
 *
 *   1. Reads the shared mutable FxRateCache with no synchronisation
 *   2. double arithmetic for rates and amounts — cross-rate division
 *      compounds representation error on every conversion
 *   3. Synthesises cross rates via USD with no spread/precision policy
 *   4. Throws a generic IllegalArgumentException when a pair is missing —
 *      callers cannot distinguish "unknown pair" from "provider outage"
 */
@Service
public class FxConversionService {

    public double convert(String fromCurrency, String toCurrency, double amount) {
        if (fromCurrency.equals(toCurrency)) {
            return amount;
        }

        Double direct = FxRateCache.RATES.get(fromCurrency + toCurrency);
        if (direct != null) {
            return amount * direct;
        }

        Double inverse = FxRateCache.RATES.get(toCurrency + fromCurrency);
        if (inverse != null) {
            // PROBLEM: double division — 1/0.79 style inversions lose precision
            return amount / inverse;
        }

        // Cross via USD
        Double fromUsd = FxRateCache.RATES.get(fromCurrency + "USD");
        Double usdTo = FxRateCache.RATES.get("USD" + toCurrency);
        if (fromUsd != null && usdTo != null) {
            return amount * fromUsd * usdTo;
        }

        throw new IllegalArgumentException("No rate available for " + fromCurrency + "/" + toCurrency);
    }
}
