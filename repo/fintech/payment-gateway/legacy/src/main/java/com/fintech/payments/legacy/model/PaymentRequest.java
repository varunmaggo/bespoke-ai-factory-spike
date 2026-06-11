package com.fintech.payments.legacy.model;

// MIGRATE TO: jakarta.validation.* (Boot 3.x / Jakarta EE 9+)
import javax.validation.constraints.DecimalMin;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Pattern;

public class PaymentRequest {

    @NotBlank
    private String merchantId;

    @NotBlank
    @Pattern(regexp = "\\d{12,19}", message = "card number must be 12-19 digits")
    private String cardNumber;

    // PROBLEM: money as double — 19.99 is not representable exactly in binary
    // floating point. MIGRATE TO: BigDecimal with explicit scale + RoundingMode.
    @DecimalMin("0.01")
    private double amount;

    @NotBlank
    @Pattern(regexp = "[A-Z]{3}")
    private String currency;

    // Client-supplied key used to de-duplicate retries of the same payment
    private String idempotencyKey;

    public PaymentRequest() {
    }

    public PaymentRequest(String merchantId, String cardNumber, double amount,
                          String currency, String idempotencyKey) {
        this.merchantId = merchantId;
        this.cardNumber = cardNumber;
        this.amount = amount;
        this.currency = currency;
        this.idempotencyKey = idempotencyKey;
    }

    public String getMerchantId() { return merchantId; }
    public void setMerchantId(String merchantId) { this.merchantId = merchantId; }
    public String getCardNumber() { return cardNumber; }
    public void setCardNumber(String cardNumber) { this.cardNumber = cardNumber; }
    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }
    public String getIdempotencyKey() { return idempotencyKey; }
    public void setIdempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; }
}
