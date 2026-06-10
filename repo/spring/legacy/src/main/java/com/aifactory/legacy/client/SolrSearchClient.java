package com.aifactory.legacy.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * LEGACY — Synchronous keyword search against a Solr index.
 *
 * Problems:
 *   1. Uses RestTemplate (blocking I/O) — ties up a thread per request
 *   2. Catches generic Exception — swallows errors silently
 *   3. No retry logic — any transient Solr failure = empty results
 *   4. No circuit breaker — if Solr is down, every request hangs for 5s
 *   5. No tracing — impossible to correlate Solr calls to upstream requests
 *   6. Keyword search only — no semantic / vector similarity
 *
 * Migration: replace with RAG service (vector + graph hybrid search via WebClient).
 */
@Component
public class SolrSearchClient {

    private static final Logger log = LoggerFactory.getLogger(SolrSearchClient.class);

    private final RestTemplate restTemplate;

    @Value("${legacy.search.url}")
    private String solrUrl;

    @Value("${legacy.search.max-results:10}")
    private int maxResults;

    public SolrSearchClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * MIGRATE TO: ragWebClient.post().uri("/retrieve")...
     *
     * Returns list of matching document IDs (no content, no score).
     * The calling service must do a second trip to fetch document content.
     */
    @SuppressWarnings("unchecked")
    public List<String> keywordSearch(String query, String department) {
        try {
            String url = UriComponentsBuilder.fromHttpUrl(solrUrl)
                    .queryParam("q", query)
                    .queryParam("fq", department != null ? "department:" + department : "*:*")
                    .queryParam("fl", "id")
                    .queryParam("rows", maxResults)
                    .queryParam("wt", "json")
                    .toUriString();

            // PROBLEM: blocking call — no timeout enforcement at this level
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);

            if (response.getBody() == null) {
                return Collections.emptyList();
            }

            Map<String, Object> responseBody = response.getBody();
            Map<String, Object> responseSection = (Map<String, Object>) responseBody.get("response");
            List<Map<String, Object>> docs = (List<Map<String, Object>>) responseSection.get("docs");

            return docs.stream()
                    .map(d -> (String) d.get("id"))
                    .toList();

        } catch (RestClientException e) {
            // PROBLEM: swallows the error — caller gets empty results with no indication of failure
            log.error("Solr search failed for query '{}': {}", query, e.getMessage());
            return Collections.emptyList();
        } catch (Exception e) {
            // PROBLEM: catches everything — masks bugs
            log.error("Unexpected error during Solr search", e);
            return Collections.emptyList();
        }
    }

    /**
     * MIGRATE TO: part of the RAG retrieve call — content comes back with the chunks.
     *
     * Fetch the text content of a document by ID.
     * Requires a second HTTP call — inefficient.
     */
    @SuppressWarnings("unchecked")
    public String fetchDocumentContent(String documentId) {
        try {
            String url = UriComponentsBuilder.fromHttpUrl(solrUrl)
                    .queryParam("q", "id:" + documentId)
                    .queryParam("fl", "id,content,title")
                    .queryParam("wt", "json")
                    .toUriString();

            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
            if (response.getBody() == null) return "";

            Map<String, Object> body = response.getBody();
            Map<String, Object> resp = (Map<String, Object>) body.get("response");
            List<Map<String, Object>> docs = (List<Map<String, Object>>) resp.get("docs");

            if (docs == null || docs.isEmpty()) return "";
            return (String) docs.get(0).getOrDefault("content", "");

        } catch (Exception e) {
            log.error("Failed to fetch document {}: {}", documentId, e.getMessage());
            return "";
        }
    }
}
