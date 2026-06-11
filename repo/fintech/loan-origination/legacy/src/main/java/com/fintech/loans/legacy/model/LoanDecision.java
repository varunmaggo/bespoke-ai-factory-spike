package com.fintech.loans.legacy.model;

public class LoanDecision {

    private String decision;     // APPROVED | REFERRED | DECLINED — stringly typed
    private double offeredApr;   // 0 when not approved
    private int bureauScore;
    // PROBLEM: no reasons list, no audit reference — "why declined?" is
    // unanswerable from this payload
    private String requestId;

    public LoanDecision() {
    }

    public LoanDecision(String decision, double offeredApr, int bureauScore, String requestId) {
        this.decision = decision;
        this.offeredApr = offeredApr;
        this.bureauScore = bureauScore;
        this.requestId = requestId;
    }

    public String getDecision() { return decision; }
    public void setDecision(String decision) { this.decision = decision; }
    public double getOfferedApr() { return offeredApr; }
    public void setOfferedApr(double offeredApr) { this.offeredApr = offeredApr; }
    public int getBureauScore() { return bureauScore; }
    public void setBureauScore(int bureauScore) { this.bureauScore = bureauScore; }
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
}
