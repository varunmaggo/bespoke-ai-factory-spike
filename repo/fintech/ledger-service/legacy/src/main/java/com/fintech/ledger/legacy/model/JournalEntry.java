package com.fintech.ledger.legacy.model;

// MIGRATE TO: jakarta.validation.*
import javax.validation.constraints.NotBlank;

public class JournalEntry {

    @NotBlank
    private String accountId;

    // PROBLEM: money as double — balances drift by fractions of a penny and
    // the EOD trial balance needs an epsilon to "balance".
    // MIGRATE TO: BigDecimal(scale 2) or minor-unit long.
    private double debit;
    private double credit;

    public JournalEntry() {
    }

    public JournalEntry(String accountId, double debit, double credit) {
        this.accountId = accountId;
        this.debit = debit;
        this.credit = credit;
    }

    public String getAccountId() { return accountId; }
    public void setAccountId(String accountId) { this.accountId = accountId; }
    public double getDebit() { return debit; }
    public void setDebit(double debit) { this.debit = debit; }
    public double getCredit() { return credit; }
    public void setCredit(double credit) { this.credit = credit; }
}
