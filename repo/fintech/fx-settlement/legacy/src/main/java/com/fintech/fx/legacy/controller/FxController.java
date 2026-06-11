package com.fintech.fx.legacy.controller;

import com.fintech.fx.legacy.service.FxConversionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/fx")
public class FxController {

    private final FxConversionService conversionService;

    public FxController(FxConversionService conversionService) {
        this.conversionService = conversionService;
    }

    @GetMapping("/convert")
    public ResponseEntity<Map<String, Object>> convert(@RequestParam String from,
                                                       @RequestParam String to,
                                                       @RequestParam double amount) {
        double converted = conversionService.convert(from, to, amount);
        // PROBLEM: no rate timestamp / staleness flag in the response
        return ResponseEntity.ok(Map.of(
                "from", from,
                "to", to,
                "amount", amount,
                "converted", converted));
    }
}
