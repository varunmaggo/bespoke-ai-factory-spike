package com.fintech.loans.legacy.model;

// MIGRATE TO: jakarta.validation.*
import javax.validation.constraints.Min;
import javax.validation.constraints.NotBlank;

public class LoanApplication {

    @NotBlank
    private String applicantId;

    @Min(1000)
    private double requestedAmount;   // PROBLEM: double for money

    @Min(6)
    private int termMonths;

    private double monthlyIncome;     // PROBLEM: double for money
    private double monthlyDebtRepayments;

    public LoanApplication() {
    }

    public LoanApplication(String applicantId, double requestedAmount, int termMonths,
                           double monthlyIncome, double monthlyDebtRepayments) {
        this.applicantId = applicantId;
        this.requestedAmount = requestedAmount;
        this.termMonths = termMonths;
        this.monthlyIncome = monthlyIncome;
        this.monthlyDebtRepayments = monthlyDebtRepayments;
    }

    public String getApplicantId() { return applicantId; }
    public void setApplicantId(String applicantId) { this.applicantId = applicantId; }
    public double getRequestedAmount() { return requestedAmount; }
    public void setRequestedAmount(double requestedAmount) { this.requestedAmount = requestedAmount; }
    public int getTermMonths() { return termMonths; }
    public void setTermMonths(int termMonths) { this.termMonths = termMonths; }
    public double getMonthlyIncome() { return monthlyIncome; }
    public void setMonthlyIncome(double monthlyIncome) { this.monthlyIncome = monthlyIncome; }
    public double getMonthlyDebtRepayments() { return monthlyDebtRepayments; }
    public void setMonthlyDebtRepayments(double monthlyDebtRepayments) { this.monthlyDebtRepayments = monthlyDebtRepayments; }
}
