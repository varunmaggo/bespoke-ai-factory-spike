package com.aifactory.legacy.model;

import java.time.LocalDateTime;
import java.util.List;

/**
 * LEGACY response model.
 * Problems:
 *   - No eval score — caller can't tell if the answer is hallucinated
 *   - No hop count or retrieval metadata
 *   - LocalDateTime instead of Instant (timezone-unaware)
 */
public class QueryResponse {

    private String answer;
    private List<String> sourceDocuments;  // just document IDs, no content or score
    private LocalDateTime timestamp;
    private String requestId;

    // No evalScore, no evalPassed, no hops, no transformMetadata

    public QueryResponse() {}

    public QueryResponse(String answer, List<String> sourceDocuments, String requestId) {
        this.answer          = answer;
        this.sourceDocuments = sourceDocuments;
        this.requestId       = requestId;
        this.timestamp       = LocalDateTime.now();
    }

    public String getAnswer()                  { return answer; }
    public List<String> getSourceDocuments()   { return sourceDocuments; }
    public LocalDateTime getTimestamp()        { return timestamp; }
    public String getRequestId()               { return requestId; }

    public void setAnswer(String answer)                        { this.answer          = answer; }
    public void setSourceDocuments(List<String> docs)           { this.sourceDocuments = docs; }
    public void setTimestamp(LocalDateTime timestamp)           { this.timestamp       = timestamp; }
    public void setRequestId(String requestId)                  { this.requestId       = requestId; }
}
