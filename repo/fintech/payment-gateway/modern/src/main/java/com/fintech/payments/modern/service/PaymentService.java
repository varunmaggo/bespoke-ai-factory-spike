package com.fintech.payments.modern.service;

import com.fintech.payments.modern.client.AcquirerClient;
import com.fintech.payments.modern.client.AcquirerUnavailableException;
import com.fintech.payments.modern.client.PanTokeniser;
import com.fintech.payments.modern.model.PaymentRequest;
import com.fintech.payments.modern.model.PaymentResponse;
import com.fintech.payments.modern.model.PaymentStatus;
import com.fintech.payments.modern.observability.PaymentMetrics;
import com.fintech.payments.modern.store.IdempotencyStore;
import io.micrometer.observation.annotation.Observed;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Map;
import java.util.UUID;

/**
 * MODERN — Card payment service, output of the fintech-java-spring2-to-spring3
 * AWS Transform migration applied to payment-gateway/legacy.
 *
 * Changes vs legacy:
 *   - IdempotencyStore port (Redis in prod) — was an in-process HashMap
 *   - BigDecimal(scale 2, HALF_EVEN) money — was double
 *   - Resilience4j circuit breaker + retry in AcquirerClient — was Thread.sleep
 *   - Typed PaymentStatus incl. ACQUIRER_UNAVAILABLE — was stringly typed
 *   - PAN tokenised + masked — was raw PAN in payloads and logs
 *   - @Observed OTel spans — was untraceable
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    private final AcquirerClient acquirerClient;
    private final IdempotencyStore idempotencyStore;
    private final PanTokeniser panTokeniser;
    private final PaymentMetrics metrics;

    public PaymentService(AcquirerClient acquirerClient,
                          IdempotencyStore idempotencyStore,
                          PanTokeniser panTokeniser,
                          PaymentMetrics metrics) {
        this.acquirerClient = acquirerClient;
        this.idempotencyStore = idempotencyStore;
        this.panTokeniser = panTokeniser;
        this.metrics = metrics;
    }

    @Observed(name = "payments.authorise", contextualName = "authorise")
    public PaymentResponse authorise(PaymentRequest request) {
        String key = request.getIdempotencyKey();

        var cached = idempotencyStore.find(key);
        if (cached.isPresent()) {
            log.info("Duplicate idempotency key {} — returning stored response", key);
            metrics.recordIdempotentReplay();
            return cached.get();
        }

        String paymentId = UUID.randomUUID().toString();
        BigDecimal amount = request.getAmount().setScale(2, RoundingMode.HALF_EVEN);
        String maskedPan = panTokeniser.mask(request.getCardNumber());
        log.info("Authorising payment paymentId={} merchant={} pan={}",
                paymentId, request.getMerchantId(), maskedPan);

        PaymentResponse response;
        long started = System.nanoTime();
        try {
            Map<String, Object> result =
                    acquirerClient.authorise(request.getCardNumber(), amount, request.getCurrency());
            metrics.recordAcquirerLatency(System.nanoTime() - started);

            PaymentStatus status = "AUTHORISED".equals(result.get("status"))
                    ? PaymentStatus.AUTHORISED
                    : PaymentStatus.DECLINED;
            String authCode = String.valueOf(result.getOrDefault("authCode", ""));
            response = new PaymentResponse(paymentId, status, authCode,
                    amount, request.getCurrency(), maskedPan);
        } catch (AcquirerUnavailableException e) {
            // Outage is distinct from a decline — caller can safely retry later
            response = new PaymentResponse(paymentId, PaymentStatus.ACQUIRER_UNAVAILABLE, null,
                    amount, request.getCurrency(), maskedPan);
        }
        metrics.recordOutcome(response.getStatus(), request.getCurrency(), amount);

        idempotencyStore.put(key, response);
        return response;
    }
}
