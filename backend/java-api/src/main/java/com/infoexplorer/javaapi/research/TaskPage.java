package com.infoexplorer.javaapi.research;

import java.time.Instant;
import java.util.List;

public record TaskPage(List<Item> items, int page, int size, boolean hasNext) {
    public record Item(String id, String question, ResearchTask.Status status,
                       Instant createdAt, Instant updatedAt) {}
}
