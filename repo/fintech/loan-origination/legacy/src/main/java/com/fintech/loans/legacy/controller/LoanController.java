package com.fintech.loans.legacy.controller;

import com.fintech.loans.legacy.model.LoanApplication;
import com.fintech.loans.legacy.model.LoanDecision;
import com.fintech.loans.legacy.service.LoanDecisionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// MIGRATE TO: jakarta.validation.Valid
import javax.validation.Valid;

@RestController
@RequestMapping("/api/v1/loans")
public class LoanController {

    private final LoanDecisionService decisionService;

    public LoanController(LoanDecisionService decisionService) {
        this.decisionService = decisionService;
    }

    @PostMapping("/decide")
    public ResponseEntity<LoanDecision> decide(@Valid @RequestBody LoanApplication application) {
        return ResponseEntity.ok(decisionService.decide(application));
    }
}
