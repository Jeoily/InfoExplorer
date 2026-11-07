package com.infoexplorer.javaapi.tracking;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.List;
import com.infoexplorer.javaapi.research.WebReport;

public final class TrackingModels {
    private TrackingModels() {}
    public record Config(@NotBlank @Size(max=160) String name,
        @NotBlank @Size(max=4000) String question,
        @NotNull @Pattern(regexp="en|zh") String language,
        @NotNull @Pattern(regexp="web|web-model") String researchMode,
        @Min(0) @Max(10080) int scheduleMinutes) {}
    public record Topic(String id, String name, String question, String language, String researchMode,
        String status, int version, int scheduleMinutes, Instant nextDueAt, Instant createdAt, Instant updatedAt) {}
    public record Cycle(String id, String topicId, int configVersion, String trigger, String taskId,
        String runId, String baselineCycleId, String status, String errorCode,
        Instant createdAt, Instant completedAt, int missedSlots) {}
    public record Change(String id, String cycleId, String taskId, String kind, boolean possibleDuplicate,
        String url, String title, String runId, String revisionId, String previousRevisionId,
        Instant discoveredAt, List<WebReport.Passage> evidence, List<WebReport.Passage> previousEvidence) {}
    public record Page<T>(List<T> items, int page, int size, boolean hasNext) {}
}
