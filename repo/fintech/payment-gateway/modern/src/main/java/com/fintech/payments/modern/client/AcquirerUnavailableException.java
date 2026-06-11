package com.fintech.payments.modern.client;

// Typed outage signal — lets callers distinguish an acquirer outage from a
// card decline (the legacy service collapsed both into a catch-all "ERROR")
public class AcquirerUnavailableException extends RuntimeException {

    public AcquirerUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
