package com.fintech.payments.modern.store;

import com.fintech.payments.modern.model.PaymentResponse;

import java.util.Optional;

/**
 * Port for idempotency state — replaces the legacy in-process synchronized
 * HashMap. Production binds the Redis adapter (shared across instances,
 * survives restarts); tests and local dev use the in-memory adapter.
 */
public interface IdempotencyStore {

    Optional<PaymentResponse> find(String idempotencyKey);

    void put(String idempotencyKey, PaymentResponse response);
}
