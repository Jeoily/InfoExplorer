package com.infoexplorer.javaapi.research;

import java.time.Instant;
import java.util.List;

public record ResearchReport(String answer, List<String> sources, String provider,
                             String query, Instant retrievedAt, List<Evidence> evidence, Generation generation, SearchPlan plan) {
    public ResearchReport(String answer, List<String> sources, String provider,
                          String query, Instant retrievedAt, List<Evidence> evidence, Generation generation) {
        this(answer, sources, provider, query, retrievedAt, evidence, generation, null);
    }
    public ResearchReport(String answer, List<String> sources, String provider,
                          String query, Instant retrievedAt, List<Evidence> evidence) {
        this(answer, sources, provider, query, retrievedAt, evidence, null);
    }
}
