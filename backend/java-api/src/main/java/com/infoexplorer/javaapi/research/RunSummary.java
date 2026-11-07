package com.infoexplorer.javaapi.research;

import java.time.Instant;

public record RunSummary(String id, int attempt, ResearchTask.Status status, Instant startedAt,
                         Instant completedAt, String errorCode, boolean retryAccepted) {}
