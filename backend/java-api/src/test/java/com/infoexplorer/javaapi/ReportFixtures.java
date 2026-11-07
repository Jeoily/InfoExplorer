package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.Evidence;
import com.infoexplorer.javaapi.research.ResearchReport;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

final class ReportFixtures {
    static ResearchReport planned(ResearchReport base) {
        var plan=new com.infoexplorer.javaapi.research.SearchPlan("model","Compare public topics",null,
            List.of(new com.infoexplorer.javaapi.research.SearchPlan.Query("public topic","en","SUCCEEDED",base.evidence().size(),
                base.evidence().stream().map(Evidence::id).toList(),null)),
            new com.infoexplorer.javaapi.research.Generation("fixture","models.example.org","search-plan-v1","a".repeat(64)));
        return new ResearchReport(base.answer(),base.sources(),base.provider(),base.query(),base.retrievedAt(),base.evidence(),base.generation(),plan);
    }
    static ResearchReport report(String answer, List<String> sources) {
        var now = Instant.parse("2026-10-14T00:00:00Z");
        var evidence = new ArrayList<Evidence>();
        try {
            for (String url : sources) {
                String text = "fixture excerpt " + evidence.size();
                String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
                evidence.add(new Evidence("E" + (evidence.size() + 1), url, "Fixture title", text, now, hash));
            }
        } catch (java.security.NoSuchAlgorithmException exception) { throw new AssertionError(exception); }
        return new ResearchReport(answer, sources, "fixture", "fixture query", now, evidence);
    }
}
