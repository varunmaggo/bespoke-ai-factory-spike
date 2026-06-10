package com.aifactory.modern.model;

// MIGRATED: javax.validation.constraints → jakarta.validation.constraints
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * MODERN request model — jakarta.validation (Spring Boot 3.x).
 *
 * AWS Transform Custom change:
 *   import javax.validation.constraints.* → import jakarta.validation.constraints.*
 */
public class QueryRequest {

    @NotBlank(message = "Query must not be blank")
    @Size(min = 3, max = 1000, message = "Query must be between 3 and 1000 characters")
    private String query;

    private String userId;

    private String department;

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
