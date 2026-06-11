package com.fintech.payments.modern.client;

import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * Tokenises the PAN before any outbound call or log line, keeping the full
 * card number out of downstream systems (PCI DSS scope reduction). The
 * legacy service sent the raw PAN to the acquirer and into its logs.
 */
@Component
public class PanTokeniser {

    public String tokenise(String pan) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(pan.getBytes(StandardCharsets.UTF_8));
            return "tok_" + HexFormat.of().formatHex(hash, 0, 16);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    public String mask(String pan) {
        String lastFour = pan.substring(pan.length() - 4);
        return "**** **** **** " + lastFour;
    }
}
