package com.fintech.payments.modern.observability;

import com.fintech.payments.modern.model.PaymentStatus;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.concurrent.TimeUnit;

/**
 * Business-level payment metrics, exported via the actuator Prometheus
 * endpoint and scraped by the OTel Collector / Prometheus.
 *
 * Series (all prefixed payments_):
 *   payments_authorised_total{currency}     counter
 *   payments_declined_total{currency}       counter
 *   payments_acquirer_unavailable_total     counter (outages, not declines)
 *   payments_idempotent_replays_total       counter (duplicate keys served from store)
 *   payments_authorised_amount_total{currency}  counter (sum of authorised value, minor units)
 *   payments_acquirer_latency_seconds       timer (acquirer round-trip, P50/P95/P99)
 *
 * Alerting on these lives in otel/prometheus-alerts.yml (high decline ratio,
 * acquirer circuit open, latency burn). The Grafana board is
 * otel/grafana/dashboards/fintech-payments.json.
 */
@Component
public class PaymentMetrics {

    private final MeterRegistry registry;
    private final Counter acquirerUnavailable;
    private final Counter idempotentReplays;
    private final Timer acquirerLatency;

    public PaymentMetrics(MeterRegistry registry) {
        this.registry = registry;
        this.acquirerUnavailable = Counter.builder("payments.acquirer.unavailable")
                .description("Payments that failed because the acquirer was unreachable (circuit open / timeouts)")
                .register(registry);
        this.idempotentReplays = Counter.builder("payments.idempotent.replays")
                .description("Requests answered from the idempotency store without an acquirer call")
                .register(registry);
        this.acquirerLatency = Timer.builder("payments.acquirer.latency")
                .description("Acquirer authorise round-trip latency")
                .publishPercentileHistogram()
                .register(registry);
    }

    public void recordOutcome(PaymentStatus status, String currency, BigDecimal amount) {
        switch (status) {
            case AUTHORISED -> {
                Counter.builder("payments.authorised")
                        .tag("currency", currency)
                        .register(registry)
                        .increment();
                Counter.builder("payments.authorised.amount")
                        .description("Sum of authorised value in minor units")
                        .tag("currency", currency)
                        .register(registry)
                        .increment(amount.movePointRight(2).doubleValue());
            }
            case DECLINED -> Counter.builder("payments.declined")
                    .tag("currency", currency)
                    .register(registry)
                    .increment();
            case ACQUIRER_UNAVAILABLE -> acquirerUnavailable.increment();
        }
    }

    public void recordIdempotentReplay() {
        idempotentReplays.increment();
    }

    public void recordAcquirerLatency(long nanos) {
        acquirerLatency.record(nanos, TimeUnit.NANOSECONDS);
    }
}
