package com.fintech.loans.legacy.service;

import com.fintech.loans.legacy.client.CreditBureauSoapClient;
import com.fintech.loans.legacy.model.LoanApplication;
import com.fintech.loans.legacy.model.LoanDecision;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

class LoanDecisionServiceTest {

    private CreditBureauSoapClient bureauClient;
    private LoanDecisionService service;

    @BeforeEach
    void setUp() {
        bureauClient = Mockito.mock(CreditBureauSoapClient.class);
        service = new LoanDecisionService(bureauClient);
    }

    private LoanApplication affordableApplication() {
        return new LoanApplication("app-1", 10_000.00, 36, 4_000.00, 300.00);
    }

    @Test
    void primeScoreAffordableLoanApproved() {
        when(bureauClient.fetchCreditScore(anyString())).thenReturn(720);
        LoanDecision d = service.decide(affordableApplication());
        assertEquals("APPROVED", d.getDecision());
        assertEquals(6.9, d.getOfferedApr());
    }

    @Test
    void lowScoreDeclined() {
        when(bureauClient.fetchCreditScore(anyString())).thenReturn(500);
        assertEquals("DECLINED", service.decide(affordableApplication()).getDecision());
    }

    @Test
    void nearPrimeScoreReferredWithLoadedApr() {
        when(bureauClient.fetchCreditScore(anyString())).thenReturn(600);
        LoanDecision d = service.decide(affordableApplication());
        assertEquals("REFERRED", d.getDecision());
        assertEquals(11.9, d.getOfferedApr());
    }

    @Test
    void excessiveDebtToIncomeDeclined() {
        when(bureauClient.fetchCreditScore(anyString())).thenReturn(720);
        LoanDecision d = service.decide(
                new LoanApplication("app-2", 10_000.00, 36, 2_000.00, 800.00));
        assertEquals("DECLINED", d.getDecision());
    }

    @Test
    void bureauParseFailureMagicNumberCausesReferral() {
        // DOCUMENTED GAP: -1 means "regex didn't match the SOAP response" —
        // indistinguishable from a thin-file applicant
        when(bureauClient.fetchCreditScore(anyString())).thenReturn(-1);
        assertEquals("REFERRED", service.decide(affordableApplication()).getDecision());
    }
}
