package com.infoexplorer.javaapi.research;

import java.util.List;

/** Versioned snapshot of a bounded model research execution, not a checkpoint. */
public record ModelSessionReport(String schemaVersion, String mode, String language, Session session) {
    public record Session(String version, String runId, String planMode, String planReason,
            Plan plan, Decision decision, Report report, String stopReason, List<Event> events,
            WebReport.Usage usage, WebReport.Outcome outcome) {}
    public record Plan(String scope, List<Question> questions, List<String> queries) {}
    public record Question(String id, String question, String evidenceNeed) {}
    public record Decision(String action, String reason, List<Coverage> coverage, List<String> queries) {}
    public record Coverage(String questionId, String state, List<String> evidenceIds, String gap) {}
    public record Report(List<Statement> claims, List<String> limitations) {}
    public record Statement(String kind, String text, List<String> evidenceIds) {}
    public record Event(String stage, String status, String code, String inputHash) {}
}
