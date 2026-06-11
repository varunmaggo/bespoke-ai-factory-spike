package com.fintech.kyc.legacy.controller;

import com.fintech.kyc.legacy.model.CustomerApplication;
import com.fintech.kyc.legacy.model.ScreeningResult;
import com.fintech.kyc.legacy.service.SanctionsScreeningService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// MIGRATE TO: jakarta.validation.Valid
import javax.validation.Valid;

@RestController
@RequestMapping("/api/v1/onboarding")
public class OnboardingController {

    private final SanctionsScreeningService screeningService;

    public OnboardingController(SanctionsScreeningService screeningService) {
        this.screeningService = screeningService;
    }

    @PostMapping("/screen")
    public ResponseEntity<ScreeningResult> screen(@Valid @RequestBody CustomerApplication application) {
        return ResponseEntity.ok(screeningService.screen(application));
    }
}
