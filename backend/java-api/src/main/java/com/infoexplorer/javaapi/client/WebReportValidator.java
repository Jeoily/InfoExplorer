package com.infoexplorer.javaapi.client;

import com.infoexplorer.javaapi.research.WebReport;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import tools.jackson.databind.json.JsonMapper;

public final class WebReportValidator {
    private WebReportValidator() {}
    private static final Set<String> ERRORS = Set.of("SEARCH_TIMEOUT", "SEARCH_UNAVAILABLE", "SEARCH_RATE_LIMITED", "SEARCH_CONFIG_ERROR",
        "SEARCH_INVALID_RESPONSE", "CONTENT_TIMEOUT", "CONTENT_UNAVAILABLE", "CONTENT_UNSUPPORTED", "CONTENT_DISALLOWED",
        "CONTENT_INVALID_RESPONSE", "SOURCE_URL_REJECTED", "SOURCE_ADDRESS_REJECTED", "CONTENT_EMPTY", "CONTENT_TOO_LARGE",
        "CONTENT_REDIRECT_REJECTED", "CONTENT_ROBOTS_UNSUPPORTED", "CONTENT_ROBOTS_UNAVAILABLE", "CONTENT_UNSUPPORTED_ENCODING",
        "CONTENT_REQUEST_LIMIT", "CONTENT_EXTRACTOR_NOT_INSTALLED", "CONTENT_EXTRACTION_FAILED", "EXECUTION_CANCELLED",
        "EXECUTION_DEADLINE", "EXECUTION_BUDGET_EXHAUSTED", "READ_LIMIT", "MODEL_TIMEOUT", "MODEL_UNAVAILABLE",
        "MODEL_INVALID_RESPONSE", "MODEL_RATE_LIMITED", "MODEL_AUTH_ERROR", "MODEL_CONFIG_ERROR", "MODEL_INPUT_TOO_LARGE", "MODEL_BUSY");
    public static void validate(WebReport r, String runId, String question, String language, JsonMapper mapper) {
        validate(r,runId,question,language,mapper,false);
    }
    static void validate(WebReport r, String runId, String question, String language, JsonMapper mapper, boolean model) {
        try {
            String normalized = question.strip().replaceAll("(?U)\\s+", " ");
            require(r != null && language.equals(r.language()) && r.questions()!=null && !r.questions().isEmpty());
            if(!model) require("web-research-v2".equals(r.schemaVersion()) && "web-extract".equals(r.mode())
                && "direct".equals(r.planMode()) && Map.of("Q1", normalized).equals(r.questions()));
            var o=r.outcome();
            require(o != null && runId.equals(o.runId()) && Set.of("SUCCEEDED","FAILED").contains(o.status())
                && (model?Set.of("unknown","partial","sufficient"):Set.of("unknown","partial")).contains(o.coverage()));
            if(!model) require(!o.reviewApplied() && (o.reviewSnapshot()==null || o.reviewSnapshot().isNull()));
            require(o.evidence()!=null && o.evidence().size()<=8 && o.sources()!=null && o.sources().size()<=(model?25:5)
                && o.queries()!=null && o.queries().size()<=(model?5:1));
            require("FAILED".equals(o.status()) ? ERRORS.contains(o.completionReason()) && o.answer()==null
                : Set.of("COMPLETED","NO_USABLE_EVIDENCE").contains(o.completionReason()) && text(o.answer(),16000));
            if ("COMPLETED".equals(o.completionReason())) require(!o.evidence().isEmpty());
            if ("NO_USABLE_EVIDENCE".equals(o.completionReason())) require(o.evidence().isEmpty());
            var u=o.usage();
            require(u!=null && u.modelCalls()>=0 && u.modelCalls()<=(model?4:0) && u.searches()>=0 && u.searches()<=(model?5:1)
                && u.documents()>=0 && u.documents()<=(model?8:5) && Double.isFinite(u.remainingSeconds())
                && u.remainingSeconds()>=0 && u.remainingSeconds()<=150 && u.searches()==o.queries().size());
            Map<String,WebReport.Source> sources=new HashMap<>();
            int attempted=0;
            for(var s:o.sources()) {
                require(s!=null && s.candidate()!=null);
                var c=s.candidate();
                require(url(c.requestedUrl()) && url(c.canonicalUrl()) && text(c.host(),253)
                    && c.host().equalsIgnoreCase(URI.create(c.canonicalUrl()).getHost())
                    && ("S"+hash(c.canonicalUrl())).equals(c.sourceId()) && sources.put(c.sourceId(),s)==null
                    && text(c.title(),512) && c.snippet()!=null && c.snippet().length()<=4000
                    && c.rank()>=1 && c.rank()<=100 && c.engines()!=null && c.engines().size()<=50
                    && c.engines().stream().allMatch(e->text(e,100)) && optional(c.publishedText(),256)
                    && Set.of("READ","FAILED","SKIPPED").contains(s.status()));
                if (!"SKIPPED".equals(s.status())) attempted++;
                if ("READ".equals(s.status())) {
                    var m=s.metadata();
                    require(s.errorCode()==null && m!=null && c.requestedUrl().equals(m.requestedUrl())
                        && url(m.resolvedUrl()) && text(m.resolvedHost(),253)
                        && m.resolvedHost().equalsIgnoreCase(URI.create(m.resolvedUrl()).getHost())
                        && Set.of("text/html","application/xhtml+xml").contains(m.contentType())
                        && m.httpRequests()>=1 && m.httpRequests()<=12 && text(m.extractor(),100)
                        && hex(m.extractedTextHash()) && "paragraph-json-v1".equals(m.normalizationVersion())
                        && optional(m.publishedText(),256)
                        && (m.publishedText()==null ? "unknown".equals(m.publishedBasis()) : "extractor_unverified".equals(m.publishedBasis())));
                    Instant.parse(m.retrievedAt());
                } else require(s.metadata()==null && ERRORS.contains(s.errorCode()));
            }
            require(attempted==u.documents());
            Set<String> found=new HashSet<>();
            for(var q:o.queries()) {
                require(q!=null && (model?text(q.query(),4000):normalized.equals(q.query())) && q.round()>=0 && q.round()<=(model?1:0) && q.sourceIds()!=null
                    && q.sourceIds().size()<=5 && new HashSet<>(q.sourceIds()).size()==q.sourceIds().size()
                    && sources.keySet().containsAll(q.sourceIds()) && q.warnings()!=null
                    && q.warnings().size()<=1 && q.warnings().stream().allMatch("SEARCH_ENGINES_PARTIALLY_UNAVAILABLE"::equals));
                if ("SUCCEEDED".equals(q.status())) require(q.errorCode()==null);
                else require("FAILED".equals(q.status()) && ERRORS.contains(q.errorCode()) && q.sourceIds().isEmpty());
                found.addAll(q.sourceIds());
            }
            require(found.equals(sources.keySet()));
            Set<String> ids=new HashSet<>(), keys=new HashSet<>();
            Map<String,Integer> counts=new HashMap<>();
            int total=0;
            for(var e:o.evidence()) {
                require(e!=null && e.evidenceId()!=null && e.evidenceId().matches("E([1-9]|1[0-6])") && ids.add(e.evidenceId())
                    && sources.containsKey(e.sourceId()) && "READ".equals(sources.get(e.sourceId()).status())
                    && e.paragraphIndex()>=0 && e.paragraphIndex()<1000 && e.offsetUtf16()>=0 && e.offsetUtf16()<=30000
                    && text(e.excerpt(),1600) && hash(e.excerpt()).equals(e.contentHash())
                    && e.matchedQuestionIds()!=null && !e.matchedQuestionIds().isEmpty()
                    && new HashSet<>(e.matchedQuestionIds()).size()==e.matchedQuestionIds().size()
                    && r.questions().keySet().containsAll(e.matchedQuestionIds())
                    && Double.isFinite(e.relevance()) && e.relevance()>=0 && e.relevance()<=1.1);
                String identity=mapper.writeValueAsString(List.of(runId,e.sourceId(),e.paragraphIndex(),e.offsetUtf16(),e.contentHash()));
                require(hash(identity).equals(e.evidenceKey()) && keys.add(e.evidenceKey()));
                require(counts.merge(e.sourceId(),1,Integer::sum)<=(model?4:2));
                total+=e.excerpt().length();
            }
            require(total<=12800);
            if(o.answer()!=null) {
                var matcher=java.util.regex.Pattern.compile("\\[(E[0-9]+)\\]").matcher(o.answer());
                while(matcher.find()) require(ids.contains(matcher.group(1)));
            }
        } catch (Exception ex) { throw new AgentException(AgentException.Reason.INVALID_RESPONSE, ex); }
    }
    static void require(boolean value) { if(!value) throw new IllegalArgumentException("Invalid web contract"); }
    static boolean text(String s,int n) { return s!=null && !s.isBlank() && s.length()<=n && s.indexOf(0)<0; }
    private static boolean optional(String s,int n) { return s==null || text(s,n); }
    private static boolean hex(String s) { return s!=null && s.matches("[a-f0-9]{64}"); }
    private static boolean url(String s) {
        if(!text(s,2048) || s.contains("\\")) return false;
        URI u=URI.create(s);
        return Set.of("http","https").contains(u.getScheme()) && u.getHost()!=null && u.getUserInfo()==null
            && (u.getPort()==-1 || u.getPort()==("https".equals(u.getScheme())?443:80));
    }
    public static String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch(Exception ex) { throw new IllegalStateException(ex); }
    }
}
