package com.fintech.fraud.legacy.model;

// MIGRATE TO: jakarta.validation.*
import javax.validation.constraints.NotBlank;

public class CardTransaction {

    @NotBlank
    private String cardId;

    private double amount;        // PROBLEM: double for money

    @NotBlank
    private String merchantCategory;

    @NotBlank
    private String country;

    private long timestampEpochMs;

    public CardTransaction() {
    }

    public CardTransaction(String cardId, double amount, String merchantCategory,
                           String country, long timestampEpochMs) {
        this.cardId = cardId;
        this.amount = amount;
        this.merchantCategory = merchantCategory;
        this.country = country;
        this.timestampEpochMs = timestampEpochMs;
    }

    public String getCardId() { return cardId; }
    public void setCardId(String cardId) { this.cardId = cardId; }
    public double getAmount() { return amount; }
    public void setAmount(double amount) { this.amount = amount; }
    public String getMerchantCategory() { return merchantCategory; }
    public void setMerchantCategory(String merchantCategory) { this.merchantCategory = merchantCategory; }
    public String getCountry() { return country; }
    public void setCountry(String country) { this.country = country; }
    public long getTimestampEpochMs() { return timestampEpochMs; }
    public void setTimestampEpochMs(long timestampEpochMs) { this.timestampEpochMs = timestampEpochMs; }
}
