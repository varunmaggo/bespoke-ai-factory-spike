package com.fintech.ledger.legacy.service;

import com.fintech.ledger.legacy.model.JournalEntry;
import com.fintech.ledger.legacy.repository.LedgerRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LedgerServiceTest {

    private LedgerService ledgerService;

    @BeforeEach
    void setUp() {
        ledgerService = new LedgerService(Mockito.mock(LedgerRepository.class));
    }

    @Test
    void balancedJournalPosts() {
        String journalId = ledgerService.postJournal(List.of(
                new JournalEntry("acc-cash", 100.00, 0.0),
                new JournalEntry("acc-revenue", 0.0, 100.00)));
        assertNotNull(journalId);
    }

    @Test
    void unbalancedJournalRejected() {
        assertThrows(IllegalArgumentException.class, () -> ledgerService.postJournal(List.of(
                new JournalEntry("acc-cash", 100.00, 0.0),
                new JournalEntry("acc-revenue", 0.0, 99.00))));
    }

    @Test
    void floatingPointJournalOnlyBalancesThanksToEpsilon() {
        // 0.10 + 0.20 != 0.30 in double arithmetic. This posting succeeds only
        // because of the BALANCE_EPSILON workaround — the modern BigDecimal
        // ledger balances exactly and needs no epsilon.
        double debitsSum = 0.10 + 0.20;
        assertTrue(debitsSum != 0.30, "double drift this test documents has disappeared");

        String journalId = ledgerService.postJournal(List.of(
                new JournalEntry("acc-a", 0.10, 0.0),
                new JournalEntry("acc-b", 0.20, 0.0),
                new JournalEntry("acc-c", 0.0, 0.30)));
        assertNotNull(journalId);
    }
}
