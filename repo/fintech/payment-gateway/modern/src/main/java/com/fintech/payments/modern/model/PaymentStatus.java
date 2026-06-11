package com.fintech.payments.modern.model;

// Typed status — replaces the stringly-typed status field in the legacy service
public enum PaymentStatus {
    AUTHORISED,
    DECLINED,
    ACQUIRER_UNAVAILABLE
}
