package com.fintech.ledger.legacy.repository;

import com.fintech.ledger.legacy.model.JournalEntry;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * LEGACY — JdbcTemplate repository with hand-built SQL.
 *
 * PROBLEM: SQL assembled by string concatenation — accountId flows straight
 *          into the statement (SQL injection); no parameter binding.
 * PROBLEM: accountHistory loads the entire posting history into memory —
 *          no pagination; large accounts OOM the JVM at month-end.
 *
 * MIGRATE TO: parameterised queries (or Spring Data JDBC) with keyset
 * pagination — see fintech-java-spring2-to-spring3 Step 5.
 */
@Repository
public class LedgerRepository {

    private final JdbcTemplate jdbcTemplate;

    public LedgerRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void insertEntry(String journalId, JournalEntry entry) {
        // PROBLEM: concatenated SQL — injectable via accountId
        String sql = "INSERT INTO ledger_entries (journal_id, account_id, debit, credit) VALUES ('"
                + journalId + "', '" + entry.getAccountId() + "', "
                + entry.getDebit() + ", " + entry.getCredit() + ")";
        jdbcTemplate.execute(sql);
    }

    public List<JournalEntry> accountHistory(String accountId) {
        // PROBLEM: injectable + unbounded result set
        String sql = "SELECT account_id, debit, credit FROM ledger_entries WHERE account_id = '"
                + accountId + "' ORDER BY id";
        return jdbcTemplate.query(sql, (rs, rowNum) -> new JournalEntry(
                rs.getString("account_id"), rs.getDouble("debit"), rs.getDouble("credit")));
    }
}
