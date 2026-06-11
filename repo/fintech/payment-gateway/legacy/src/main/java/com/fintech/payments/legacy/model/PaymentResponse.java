package com.fintech.payments.legacy.model;

// PROBLEM: LocalDateTime is timezone-unaware — settlement cut-off disputes
// across regions. MIGRATE TO: java.time.Instant (UTC).
import java.time.LocalDateTime;

public class PaymentResponse {

    private String paymentId;
    private String status;        // AUTHORISED | DECLINED | ERROR — stringly typed
    private String authCode;
    private double amount;        // PROBLEM: double for money
    private String currency;
    private LocalDateTime timestamp;

    public PaymentResponse() {
    }

    public PaymentResponse(String paymentId, String status, String authCode,
                           double amount, String currency) {
        this.paymentId = paymentId;
        this.status = status;
        this.authCode = authCode;
        this.amount = amount;
        this.currency = currency;
        this.timestamp = LocalDateTime.now();
    }

    public String getPaymentId() { return paymentId; }
    public void setPaymentId(String paymentId) { this.paymentId = paymentId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getAuthCode() { return authCode; }
    public void setAuthCode(String authCode) { this.authCode = authCode; }
    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }
    public LocalDateTime getTimestamp() { return timestamp; }
    public void setTimestamp(LocalDateTime timestamp) { this.timestamp = timestamp; }
}
