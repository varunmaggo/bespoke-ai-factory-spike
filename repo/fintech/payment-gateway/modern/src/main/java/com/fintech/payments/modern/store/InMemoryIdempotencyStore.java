package com.fintech.payments.modern.store;

import com.fintech.payments.modern.model.PaymentResponse;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Component
@ConditionalOnProperty(name = "payments.idempotency.store", havingValue = "memory", matchIfMissing = true)
public class InMemoryIdempotencyStore implements IdempotencyStore {

    private final Map<String, PaymentResponse> store = new ConcurrentHashMap<>();

    @Override
    public Optional<PaymentResponse> find(String idempotencyKey) {
        return Optional.ofNullable(store.get(idempotencyKey));
    }

    @Override
    public void put(String idempotencyKey, PaymentResponse response) {
        store.put(idempotencyKey, response);
    }
}
