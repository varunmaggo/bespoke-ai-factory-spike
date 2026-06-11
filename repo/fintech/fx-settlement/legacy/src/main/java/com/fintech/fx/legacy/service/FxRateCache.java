package com.fintech.fx.legacy.service;

import java.util.HashMap;
import java.util.Map;

/**
 * LEGACY — Global mutable rate cache.
 *
 * PROBLEM: public static HashMap — every class in the JVM can mutate it;
 *          the @Scheduled poller writes while request threads read with no
 *          synchronisation (visibility + race bugs under load).
 * PROBLEM: no timestamps — callers cannot tell a live rate from one that is
 *          six hours stale because the provider has been down all morning.
 *
 * MIGRATE TO: immutable rate snapshot (record) swapped atomically via
 * AtomicReference, with publishedAt + staleness flag per quote — see
 * fintech-java-spring2-to-spring3 Step 7.
 */
public final class FxRateCache {

    // Key "GBPUSD" → rate as double. PROBLEM: double for rates.
    public static final Map<String, Double> RATES = new HashMap<>();

    private FxRateCache() {
    }
}
