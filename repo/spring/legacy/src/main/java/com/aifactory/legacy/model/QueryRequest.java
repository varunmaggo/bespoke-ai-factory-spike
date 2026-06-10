package com.aifactory.legacy.model;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

/**
 * LEGACY — uses javax.validation (not jakarta.validation).
 * Migration: change to jakarta.validation.* (Spring Boot 3.x).
 */
public class QueryRequest {

    @NotBlank(message = "Query must not be blank")
    @Size(min = 3, max = 1000, message = "Query must be between 3 and 1000 characters")
    private String query;

    private String userId;

    private String department;  // used to filter Solr results

    public QueryRequest() {}

    public QueryRequest(String query, String userId, String department) {
        this.query      = query;
        this.userId     = userId;
        this.department = department;
    }

    public String getQuery()      { return query; }
    public String getUserId()     { return userId; }
    public String getDepartment() { return department; }

    public void setQuery(String query)           { this.query      = query; }
    public void setUserId(String userId)         { this.userId     = userId; }
    public void setDepartment(String department) { this.department = department; }
}
