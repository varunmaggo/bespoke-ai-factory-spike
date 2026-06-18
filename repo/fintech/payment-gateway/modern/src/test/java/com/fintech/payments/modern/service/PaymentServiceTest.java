package com.fintech.payments.modern.service;

import com.fintech.payments.modern.client.AcquirerClient;
import com.fintech.payments.modern.client.AcquirerUnavailableException;
import com.fintech.payments.modern.client.PanTokeniser;
import com.fintech.payments.modern.model.PaymentRequest;
import com.fintech.payments.modern.model.PaymentResponse;
import com.fintech.payments.modern.model.PaymentStatus;
import com.fintech.payments.modern.observability.PaymentMetrics;
import com.fintech.payments.modern.store.InMemoryIdempotencyStore;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.math.BigDecimal;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mirrors the behaviour-parity scenarios in
 * payment-gateway/legacy/.../PaymentServiceTest.java, plus assertions for
 * behaviour the legacy service could not provide (typed outage status,
 * exact money arithmetic, masked PAN).
 */
class PaymentServiceTest {

    private AcquirerClient acquirerClient;
    private PaymentService paymentService;
    private SimpleMeterRegistry meterRegistry;

    @BeforeEach
    void setUp() {
        acquirerClient = Mockito.mock(AcquirerClient.class);
        meterRegistry = new SimpleMeterRegistry();
        paymentService = new PaymentService(
                acquirerClient, new InMemoryIdempotencyStore(), new PanTokeniser(),
                new PaymentMetrics(meterRegistry));
    }

    private PaymentRequest request(String amount, String idempotencyKey) {
        return new PaymentRequest("m-1", "4111111111111111",
                new BigDecimal(amount), "GBP", idempotencyKey);
    }

    @Test
    void authorisesPaymentWhenAcquirerApproves() {
        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentResponse response = paymentService.authorise(request("19.99", "idem-1"));

        assertEquals(PaymentStatus.AUTHORISED, response.getStatus());
        assertEquals("A1B2C3", response.getAuthCode());
        // Exact decimal money — 19.99 stays 19.99 (was lossy double in legacy)
        assertEquals(new BigDecimal("19.99"), response.getAmount());
    }

    @Test
    void duplicateIdempotencyKeyReturnsStoredResponseWithoutSecondAcquirerCall() {
        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentRequest request = request("50.00", "idem-dup");
        PaymentResponse first = paymentService.authorise(request);
        PaymentResponse second = paymentService.authorise(request);

        assertEquals(first.getPaymentId(), second.getPaymentId());
        verify(acquirerClient, times(1)).authorise(anyString(), any(), anyString());
    }

    @Test
    void acquirerOutageReturnsTypedUnavailableStatus() {
        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenThrow(new AcquirerUnavailableException("Acquirer unavailable", null));

        PaymentResponse response = paymentService.authorise(request("10.00", "idem-2"));

        // Outage is distinguishable from a decline — fixed vs legacy "ERROR"
        assertEquals(PaymentStatus.ACQUIRER_UNAVAILABLE, response.getStatus());
    }

    @Test
    void responseNeverContainsFullPan() {
        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentResponse response = paymentService.authorise(request("5.00", "idem-3"));

        assertEquals("**** **** **** 1111", response.getMaskedPan());
        assertFalse(response.getMaskedPan().contains("4111111111111111"));
    }

    @Test
    void businessMetricsAreRecordedPerOutcome() {
        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentRequest request = request("19.99", "idem-metrics");
        paymentService.authorise(request);   // hits the acquirer
        paymentService.authorise(request);   // idempotent replay, no acquirer call

        assertEquals(1.0, meterRegistry.counter("payments.authorised", "currency", "GBP").count());
        assertEquals(1.0, meterRegistry.counter("payments.idempotent.replays").count());
        // 19.99 GBP authorised → 1999 minor units on the value counter
        assertEquals(1999.0, meterRegistry.counter("payments.authorised.amount", "currency", "GBP").count());
        assertEquals(1, meterRegistry.timer("payments.acquirer.latency").count());

        when(acquirerClient.authorise(anyString(), any(), anyString()))
                .thenThrow(new AcquirerUnavailableException("down", null));
        paymentService.authorise(request("5.00", "idem-metrics-2"));

        assertEquals(1.0, meterRegistry.counter("payments.acquirer.unavailable").count());
    }
}
