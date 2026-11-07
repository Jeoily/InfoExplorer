package com.infoexplorer.javaapi.research;

import java.time.Instant;

public record ResearchTask(
        String id, String question, Status status, Instant createdAt, Instant updatedAt,
        String runId, Instant startedAt, Instant completedAt, ResearchReport result, String errorCode, String language,
        String researchMode, WebReport webResult, ModelSessionReport modelSession) {
    public enum Status { PENDING, RUNNING, SUCCEEDED, FAILED }
}
