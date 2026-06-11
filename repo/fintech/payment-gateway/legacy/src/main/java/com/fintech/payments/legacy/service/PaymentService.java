package com.fintech.payments.legacy.service;

import com.fintech.payments.legacy.client.AcquirerClient;
import com.fintech.payments.legacy.model.PaymentRequest;
import com.fintech.payments.legacy.model.PaymentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * LEGACY — Synchronous card payment service.
 *
 * Problems this class demonstrates (all fixed in payment-gateway/modern):
 *
 *   1. In-memory synchronized HashMap for idempotency — lost on restart,
 *      not shared across instances; duplicate captures after a deploy
 *   2. Money as double — floating-point rounding on amounts
 *   3. Blocking acquirer call with Thread.sleep retry — no circuit breaker
 *   4. PAN handled raw — no tokenisation (PCI DSS scope blowout)
 *   5. No OTel tracing — payment journeys cannot be correlated
 *   6. Stringly-typed status — typos compile fine
 *
 * AWS Transform Custom migration (fintech-java-spring2-to-spring3):
 *   - Replace idempotency map with IdempotencyStore port (Redis adapter)
 *   - double → BigDecimal(scale 2, HALF_EVEN) for all money fields
 *   - RestTemplate retry loop → WebClient + Resilience4j
 *   - Add @Observed spans; tokenise PAN before outbound calls
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    private final AcquirerClient acquirerClient;

    // PROBLEM: idempotency state in process memory. A restart or a second
    // instance behind the load balancer silently allows duplicate payments.
    private final Map<String, PaymentResponse> processedPayments = new HashMap<>();

    public PaymentService(AcquirerClient acquirerClient) {
        this.acquirerClient = acquirerClient;
    }

    public PaymentResponse authorise(PaymentRequest request) {
        String key = request.getIdempotencyKey();

        // PROBLEM: coarse lock around the whole authorisation — serialises
        // every payment in the JVM behind a single monitor.
        synchronized (processedPayments) {
            if (key != null && processedPayments.containsKey(key)) {
                log.info("Duplicate idempotency key {} — returning cached response", key);
                return processedPayments.get(key);
            }
        }

        String paymentId = UUID.randomUUID().toString();
        log.info("Authorising payment paymentId={} merchant={}", paymentId, request.getMerchantId());

        PaymentResponse response;
        try {
            Map<String, Object> acquirerResult =
                    acquirerClient.authorise(request.getCardNumber(), request.getAmount(), request.getCurrency());

            String status = String.valueOf(acquirerResult.getOrDefault("status", "DECLINED"));
            String authCode = String.valueOf(acquirerResult.getOrDefault("authCode", ""));
            response = new PaymentResponse(paymentId, status, authCode,
                    request.getAmount(), request.getCurrency());
        } catch (Exception e) {
            // PROBLEM: catch-all; caller cannot distinguish a decline from an outage
            log.error("Authorisation failed paymentId={}: {}", paymentId, e.getMessage());
            response = new PaymentResponse(paymentId, "ERROR", null,
                    request.getAmount(), request.getCurrency());
        }

        synchronized (processedPayments) {
            if (key != null) {
                processedPayments.put(key, response);
            }
        }
        return response;
    }
}
