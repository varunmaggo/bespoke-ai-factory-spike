package com.aifactory.modern.model;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * MODERN response model — richer than legacy.
 *
 * Added vs legacy QueryResponse:
 *   - evalScore       : LLM judge score 0.0–1.0
 *   - evalPassed      : true if score ≥ configured threshold (0.75)
 *   - hops            : number of RAG retrieval iterations performed
 *   - transformMetadata: AWS Transform Custom output (definition, items_transformed, etc.)
 *   - timestamp       : Instant (UTC) instead of LocalDateTime (timezone-unaware)
 *   - sources         : List of SourceDocument (id + score + excerpt) vs bare IDs
 */
public class QueryResponse {

    private String requestId;
    private String answer;
    private List<SourceDocument> sources;
    private double evalScore;
    private boolean evalPassed;
    private int hops;
    private Map<String, Object> transformMetadata;
    private Instant timestamp;

    public QueryResponse() {}

    public QueryResponse(
            String requestId,
            String answer,
            List<SourceDocument> sources,
            double evalScore,
            boolean evalPassed,
            int hops,
            Map<String, Object> transformMetadata) {
        this.requestId         = requestId;
        this.answer            = answer;
        this.sources           = sources;
        this.evalScore         = evalScore;
        this.evalPassed        = evalPassed;
        this.hops              = hops;
        this.transformMetadata = transformMetadata;
        this.timestamp         = Instant.now();
    }

    // ── Getters ──────────────────────────────────────────────────────────────
    public String getRequestId()                    { return requestId; }
    public String getAnswer()                       { return answer; }
    public List<SourceDocument> getSources()        { return sources; }
    public double getEvalScore()                    { return evalScore; }
    public boolean isEvalPassed()                   { return evalPassed; }
    public int getHops()                            { return hops; }
    public Map<String, Object> getTransformMetadata() { return transformMetadata; }
    public Instant getTimestamp()                   { return timestamp; }

    // ── Setters ──────────────────────────────────────────────────────────────
    public void setRequestId(String requestId)         { this.requestId = requestId; }
    public void setAnswer(String answer)               { this.answer = answer; }
    public void setSources(List<SourceDocument> s)     { this.sources = s; }
    public void setEvalScore(double evalScore)         { this.evalScore = evalScore; }
    public void setEvalPassed(boolean evalPassed)      { this.evalPassed = evalPassed; }
    public void setHops(int hops)                      { this.hops = hops; }
    public void setTransformMetadata(Map<String, Object> m) { this.transformMetadata = m; }
    public void setTimestamp(Instant timestamp)        { this.timestamp = timestamp; }

    // ── Nested ────────────────────────────────────────────────────────────────
    public record SourceDocument(String id, double score, String excerpt) {}
}
