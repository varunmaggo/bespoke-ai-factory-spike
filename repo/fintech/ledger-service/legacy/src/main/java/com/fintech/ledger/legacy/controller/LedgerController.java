package com.fintech.ledger.legacy.controller;

import com.fintech.ledger.legacy.model.JournalEntry;
import com.fintech.ledger.legacy.service.LedgerService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// MIGRATE TO: jakarta.validation.Valid
import javax.validation.Valid;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/ledger")
public class LedgerController {

    private final LedgerService ledgerService;

    public LedgerController(LedgerService ledgerService) {
        this.ledgerService = ledgerService;
    }

    @PostMapping("/journals")
    public ResponseEntity<Map<String, String>> postJournal(@Valid @RequestBody List<JournalEntry> entries) {
        String journalId = ledgerService.postJournal(entries);
        return ResponseEntity.ok(Map.of("journalId", journalId));
    }

    @GetMapping("/accounts/{accountId}/balance")
    public ResponseEntity<Map<String, Object>> balance(@PathVariable String accountId) {
        return ResponseEntity.ok(Map.of(
                "accountId", accountId,
                "balance", ledgerService.accountBalance(accountId)));
    }
}
