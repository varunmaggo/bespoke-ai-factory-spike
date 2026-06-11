package com.fintech.payments.modern.model;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

import java.math.BigDecimal;

public class PaymentRequest {

    @NotBlank
    private String merchantId;

    @NotBlank
    @Pattern(regexp = "\\d{12,19}", message = "card number must be 12-19 digits")
    private String cardNumber;

    // BigDecimal — exact decimal arithmetic for money (was double in legacy)
    @NotNull
    @DecimalMin("0.01")
    private BigDecimal amount;

    @NotBlank
    @Pattern(regexp = "[A-Z]{3}")
    private String currency;

    @NotBlank
    private String idempotencyKey;

    public PaymentRequest() {
    }

    public PaymentRequest(String merchantId, String cardNumber, BigDecimal amount,
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
    public BigDecimal getAmount() { return amount; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }
    public String getIdempotencyKey() { return idempotencyKey; }
    public void setIdempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; }
}
