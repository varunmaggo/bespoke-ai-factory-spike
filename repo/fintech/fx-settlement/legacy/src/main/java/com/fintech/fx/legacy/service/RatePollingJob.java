package com.fintech.fx.legacy.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

/**
 * LEGACY — Scheduled rate poller.
 *
 * PROBLEM: RestTemplate polling with Thread.sleep backoff inside the
 *          scheduled method — blocks the (single, by default) scheduler
 *          thread, delaying every other @Scheduled job in the JVM.
 * PROBLEM: single provider, no failover; on outage the static cache simply
 *          keeps serving yesterday's rates with no staleness marker.
 *
 * MIGRATE TO: event-driven rate stream (provider webhook / Kinesis) with
 * provider failover and atomically swapped immutable snapshots.
 */
@Component
public class RatePollingJob {

    private static final Logger log = LoggerFactory.getLogger(RatePollingJob.class);

    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${fx.provider.url:http://localhost:9997/rates}")
    private String providerUrl;

    @Scheduled(fixedDelayString = "${fx.poll-interval-ms:30000}")
    @SuppressWarnings("unchecked")
    public void pollRates() {
        for (int attempt = 1; attempt <= 3; attempt++) {
            try {
                Map<String, Double> rates = restTemplate.getForObject(providerUrl, Map.class);
                if (rates != null) {
                    // PROBLEM: piecemeal mutation of the shared map — readers can
                    // observe a half-updated rate set mid-loop
                    for (Map.Entry<String, Double> entry : rates.entrySet()) {
                        FxRateCache.RATES.put(entry.getKey(), entry.getValue());
                    }
                    log.info("Refreshed {} FX rates", rates.size());
                }
                return;
            } catch (Exception e) {
                log.warn("Rate poll failed attempt={}: {}", attempt, e.getMessage());
                try {
                    Thread.sleep(2000L * attempt); // blocks the scheduler thread
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
        log.error("Rate poll failed after 3 attempts — serving stale rates with no staleness flag");
    }
}
