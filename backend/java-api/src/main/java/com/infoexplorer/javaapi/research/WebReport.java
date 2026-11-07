package com.infoexplorer.javaapi.research;

import java.util.List;
import java.util.Map;
import tools.jackson.databind.JsonNode;

/** Stored execution snapshot; intentionally separate from the historical Wiki report. */
public record WebReport(String schemaVersion, String mode, String language, String planMode,
                        Map<String,String> questions, Outcome outcome) {
    public record Outcome(String status, String completionReason, String coverage, String answer,
            List<Passage> evidence, List<Query> queries, List<Source> sources, Usage usage,
            boolean reviewApplied, String runId, JsonNode reviewSnapshot) {}
    public record Passage(String evidenceId, String sourceId, int paragraphIndex, int offsetUtf16,
            String excerpt, String contentHash, List<String> matchedQuestionIds, double relevance,
            boolean truncated, String evidenceKey) {}
    public record Query(String query, int round, String status, List<String> sourceIds,
            List<String> warnings, String errorCode) {}
    public record Source(Candidate candidate, String status, String errorCode, Metadata metadata) {}
    public record Candidate(String sourceId, String requestedUrl, String canonicalUrl, String host,
            String title, String snippet, int rank, List<String> engines, String publishedText) {}
    public record Metadata(String requestedUrl, String resolvedUrl, String resolvedHost, String retrievedAt,
            String contentType, int httpRequests, String extractor, String publishedText,
            String publishedBasis, boolean truncated, String extractedTextHash, String normalizationVersion) {}
    public record Usage(int searches, int documents, int modelCalls, double remainingSeconds, boolean cancelled) {}
}
