package com.fintech.ledger.legacy.service;

import com.fintech.ledger.legacy.model.JournalEntry;
import com.fintech.ledger.legacy.repository.LedgerRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

/**
 * LEGACY — Double-entry posting service.
 *
 * Problems this class demonstrates:
 *
 *   1. Money as double — the trial-balance check needs an epsilon because
 *      0.10 + 0.20 != 0.30 in binary floating point
 *   2. Posting loop is not transactional — a crash mid-journal leaves a
 *      half-posted (unbalanced) ledger
 *   3. No idempotency — replaying a journal double-posts it
 *   4. No OTel tracing, no structured audit trail
 *
 * AWS Transform Custom migration (fintech-java-spring2-to-spring3):
 *   - double → BigDecimal(scale 2, HALF_EVEN); drop the epsilon entirely
 *   - Wrap posting in @Transactional with journal-level idempotency key
 *   - Parameterised SQL in the repository
 *   - Add @Observed spans and an immutable audit event per journal
 */
@Service
public class LedgerService {

    private static final Logger log = LoggerFactory.getLogger(LedgerService.class);

    // PROBLEM: epsilon to paper over floating-point drift. With BigDecimal
    // the balance check is exact and this constant disappears.
    private static final double BALANCE_EPSILON = 0.001;

    private final LedgerRepository ledgerRepository;

    public LedgerService(LedgerRepository ledgerRepository) {
        this.ledgerRepository = ledgerRepository;
    }

    public String postJournal(List<JournalEntry> entries) {
        if (entries == null || entries.isEmpty()) {
            throw new IllegalArgumentException("Journal must contain at least one entry");
        }

        double totalDebits = 0.0;
        double totalCredits = 0.0;
        for (JournalEntry entry : entries) {
            totalDebits += entry.getDebit();
            totalCredits += entry.getCredit();
        }

        // PROBLEM: |debits - credits| < epsilon instead of an exact equality —
        // sub-epsilon imbalances are silently posted and accumulate.
        if (Math.abs(totalDebits - totalCredits) > BALANCE_EPSILON) {
            throw new IllegalArgumentException(String.format(
                    "Journal does not balance: debits=%.4f credits=%.4f", totalDebits, totalCredits));
        }

        String journalId = UUID.randomUUID().toString();
        // PROBLEM: no transaction — a failure on entry N leaves entries 1..N-1 posted
        for (JournalEntry entry : entries) {
            ledgerRepository.insertEntry(journalId, entry);
        }
        log.info("Posted journal {} with {} entries", journalId, entries.size());
        return journalId;
    }

    public double accountBalance(String accountId) {
        List<JournalEntry> history = ledgerRepository.accountHistory(accountId);
        double balance = 0.0;
        for (JournalEntry entry : history) {
            // PROBLEM: cumulative double arithmetic — drift grows with volume
            balance += entry.getDebit() - entry.getCredit();
        }
        return balance;
    }

    /** Used by the EOD batch — returns true when the whole ledger balances. */
    public boolean trialBalances(List<JournalEntry> allEntries) {
        double net = 0.0;
        for (JournalEntry entry : allEntries) {
            net += entry.getDebit() - entry.getCredit();
        }
        return Math.abs(net) <= BALANCE_EPSILON;
    }
}
