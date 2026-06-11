package com.fintech.fraud.legacy.model;

import java.util.List;

public class FraudAssessment {

    private boolean flagged;
    private int score;                  // PROBLEM: opaque additive score, uncalibrated
    private List<String> triggeredRules; // PROBLEM: rule IDs only — no human-readable
                                         // explanation; disputed declines can't be justified

    public FraudAssessment() {
    }

    public FraudAssessment(boolean flagged, int score, List<String> triggeredRules) {
        this.flagged = flagged;
        this.score = score;
        this.triggeredRules = triggeredRules;
    }

    public boolean isFlagged() { return flagged; }
    public void setFlagged(boolean flagged) { this.flagged = flagged; }
    public int getScore() { return score; }
    public void setScore(int score) { this.score = score; }
    public List<String> getTriggeredRules() { return triggeredRules; }
    public void setTriggeredRules(List<String> triggeredRules) { this.triggeredRules = triggeredRules; }
}
