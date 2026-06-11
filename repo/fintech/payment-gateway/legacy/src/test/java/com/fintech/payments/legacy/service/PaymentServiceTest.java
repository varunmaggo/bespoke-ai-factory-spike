package com.fintech.payments.legacy.service;

import com.fintech.payments.legacy.client.AcquirerClient;
import com.fintech.payments.legacy.model.PaymentRequest;
import com.fintech.payments.legacy.model.PaymentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Behaviour-parity tests. The same scenarios are asserted against the modern
 * service (payment-gateway/modern) after the AWS Transform migration, proving
 * the transformation preserved business behaviour.
 */
class PaymentServiceTest {

    private AcquirerClient acquirerClient;
    private PaymentService paymentService;

    @BeforeEach
    void setUp() {
        acquirerClient = Mockito.mock(AcquirerClient.class);
        paymentService = new PaymentService(acquirerClient);
    }

    @Test
    void authorisesPaymentWhenAcquirerApproves() {
        when(acquirerClient.authorise(anyString(), anyDouble(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentResponse response = paymentService.authorise(
                new PaymentRequest("m-1", "4111111111111111", 19.99, "GBP", "idem-1"));

        assertEquals("AUTHORISED", response.getStatus());
        assertEquals("A1B2C3", response.getAuthCode());
    }

    @Test
    void duplicateIdempotencyKeyReturnsCachedResponseWithoutSecondAcquirerCall() {
        when(acquirerClient.authorise(anyString(), anyDouble(), anyString()))
                .thenReturn(Map.of("status", "AUTHORISED", "authCode", "A1B2C3"));

        PaymentRequest request = new PaymentRequest("m-1", "4111111111111111", 50.00, "GBP", "idem-dup");
        PaymentResponse first = paymentService.authorise(request);
        PaymentResponse second = paymentService.authorise(request);

        assertEquals(first.getPaymentId(), second.getPaymentId());
        verify(acquirerClient, times(1)).authorise(anyString(), anyDouble(), anyString());
    }

    @Test
    void acquirerOutageReturnsErrorStatusNotException() {
        when(acquirerClient.authorise(anyString(), anyDouble(), anyString()))
                .thenThrow(new IllegalStateException("Acquirer unavailable after 3 attempts"));

        PaymentResponse response = paymentService.authorise(
                new PaymentRequest("m-1", "4111111111111111", 10.00, "GBP", null));

        // PROBLEM demonstrated: caller cannot distinguish decline from outage
        assertEquals("ERROR", response.getStatus());
        assertNotEquals("DECLINED", response.getStatus());
    }
}
