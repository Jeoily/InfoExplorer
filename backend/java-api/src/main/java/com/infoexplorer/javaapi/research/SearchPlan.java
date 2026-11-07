package com.infoexplorer.javaapi.research;

import java.util.List;

public record SearchPlan(String mode, String intent, String reason, List<Query> queries, Generation generation) {
    public record Query(String query, String language, String status, int resultCount,
                        List<String> evidenceIds, String errorCode) {}
}
