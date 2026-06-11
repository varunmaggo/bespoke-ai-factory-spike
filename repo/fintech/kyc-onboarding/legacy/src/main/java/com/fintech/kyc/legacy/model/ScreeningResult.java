package com.fintech.kyc.legacy.model;

import java.util.List;

public class ScreeningResult {

    // PROBLEM: binary decision, no risk score, no narrative — an analyst
    // reviewing a BLOCK has no idea which evidence drove it.
    // The agentic version returns: riskScore, matchedEntities with
    // similarity + source documents, a cited narrative, and an evalScore.
    private boolean blocked;
    private List<String> matchedNames;

    public ScreeningResult() {
    }

    public ScreeningResult(boolean blocked, List<String> matchedNames) {
        this.blocked = blocked;
        this.matchedNames = matchedNames;
    }

    public boolean isBlocked() { return blocked; }
    public void setBlocked(boolean blocked) { this.blocked = blocked; }
    public List<String> getMatchedNames() { return matchedNames; }
    public void setMatchedNames(List<String> matchedNames) { this.matchedNames = matchedNames; }
}
