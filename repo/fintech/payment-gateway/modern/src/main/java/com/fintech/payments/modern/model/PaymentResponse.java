package com.fintech.payments.modern.model;

import java.math.BigDecimal;
import java.time.Instant;

public class PaymentResponse {

    private String paymentId;
    private PaymentStatus status;
    private String authCode;
    private BigDecimal amount;
    private String currency;
    // Instant (UTC) — replaces timezone-unaware LocalDateTime in legacy
    private Instant timestamp;
    // Last four digits only — full PAN never leaves the tokeniser
    private String maskedPan;

    public PaymentResponse() {
    }

    public PaymentResponse(String paymentId, PaymentStatus status, String authCode,
                           BigDecimal amount, String currency, String maskedPan) {
        this.paymentId = paymentId;
        this.status = status;
        this.authCode = authCode;
        this.amount = amount;
        this.currency = currency;
        this.maskedPan = maskedPan;
        this.timestamp = Instant.now();
    }

    public String getPaymentId() { return paymentId; }
    public void setPaymentId(String paymentId) { this.paymentId = paymentId; }
    public PaymentStatus getStatus() { return status; }
    public void setStatus(PaymentStatus status) { this.status = status; }
    public String getAuthCode() { return authCode; }
    public void setAuthCode(String authCode) { this.authCode = authCode; }
    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }
    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
    public String getMaskedPan() { return maskedPan; }
    public void setMaskedPan(String maskedPan) { this.maskedPan = maskedPan; }
}
