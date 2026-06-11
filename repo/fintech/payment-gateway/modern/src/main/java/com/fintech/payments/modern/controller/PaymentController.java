package com.fintech.payments.modern.controller;

import com.fintech.payments.modern.model.PaymentRequest;
import com.fintech.payments.modern.model.PaymentResponse;
import com.fintech.payments.modern.service.PaymentService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/payments")
public class PaymentController {

    private final PaymentService paymentService;

    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    @PostMapping("/authorise")
    public ResponseEntity<PaymentResponse> authorise(@Valid @RequestBody PaymentRequest request) {
        return ResponseEntity.ok(paymentService.authorise(request));
    }
}
