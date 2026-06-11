package com.fintech.fraud.legacy.controller;

import com.fintech.fraud.legacy.model.CardTransaction;
import com.fintech.fraud.legacy.model.FraudAssessment;
import com.fintech.fraud.legacy.service.FraudRuleEngine;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// MIGRATE TO: jakarta.validation.Valid
import javax.validation.Valid;

@RestController
@RequestMapping("/api/v1/fraud")
public class FraudController {

    private final FraudRuleEngine fraudRuleEngine;

    public FraudController(FraudRuleEngine fraudRuleEngine) {
        this.fraudRuleEngine = fraudRuleEngine;
    }

    @PostMapping("/assess")
    public ResponseEntity<FraudAssessment> assess(@Valid @RequestBody CardTransaction transaction) {
        return ResponseEntity.ok(fraudRuleEngine.assess(transaction));
    }
}
