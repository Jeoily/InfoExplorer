package com.infoexplorer.javaapi.client;

import com.infoexplorer.javaapi.dto.ChatRequest;
import com.infoexplorer.javaapi.dto.ResearchRequest;
import com.infoexplorer.javaapi.dto.ChatResponse;
import com.infoexplorer.javaapi.research.ResearchReport;
import java.util.HashSet;
import java.util.Set;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.net.SocketTimeoutException;
import java.net.URI;
import java.time.Duration;
import tools.jackson.databind.json.JsonMapper;

@Component
public class AgentClient {
    private final RestClient client;
    private final RestClient researchClient;
    private final JsonMapper mapper;

    public AgentClient(
            @Value("${agent.service.base-url}") String baseUrl,
            @Value("${agent.service.connect-timeout-ms}") int connectTimeoutMs,
            @Value("${agent.service.read-timeout-ms}") int readTimeoutMs,
            @Value("${agent.service.research-read-timeout-ms}") int researchReadTimeoutMs,
            JsonMapper mapper) {
        this.mapper = mapper;
        URI uri = URI.create(baseUrl);
        if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
                || uri.getHost() == null || uri.getUserInfo() != null
                || uri.getQuery() != null || uri.getFragment() != null) {
            throw new IllegalArgumentException("Agent base URL must be an HTTP(S) URL without credentials, query or fragment");
        }
        if (connectTimeoutMs <= 0 || readTimeoutMs <= 0 || researchReadTimeoutMs <= 0) {
            throw new IllegalArgumentException("Agent timeouts must be positive");
        }
        client = buildClient(baseUrl, connectTimeoutMs, readTimeoutMs, mapper);
        researchClient = buildClient(baseUrl, connectTimeoutMs, researchReadTimeoutMs, mapper);
    }

    private RestClient buildClient(String baseUrl, int connectTimeoutMs, int readTimeoutMs, JsonMapper mapper) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(connectTimeoutMs));
        factory.setReadTimeout(Duration.ofMillis(readTimeoutMs));
        return RestClient.builder().baseUrl(baseUrl).requestFactory(factory)
                .configureMessageConverters(converters ->
                        converters.withJsonConverter(new JacksonJsonHttpMessageConverter(mapper)))
                .build();
    }

    public ChatResponse ask(ChatRequest request) {
        ChatResponse response = call("/internal/v1/agent/run", request, ChatResponse.class);
        if (response == null || response.answer() == null || response.answer().isBlank()
                || response.sources() == null
                || response.sources().stream().anyMatch(source -> source == null || source.isBlank())) {
            throw new AgentException(AgentException.Reason.INVALID_RESPONSE, null);
        }
        return response;
    }

    public ResearchReport research(ResearchRequest request) {
        ResearchReport report = call("/internal/v1/research/run", java.util.Map.of("question", request.question(), "language", request.language()), ResearchReport.class);
        validateReport(report);
        validatePlan(report, request);
        return report;
    }
    public void validateControlled(ResearchReport report,ResearchRequest request) {
        validateReport(report); validatePlan(report,request);
    }

    private void validatePlan(ResearchReport report, ResearchRequest request) {
        var plan = report.plan();
        if (plan == null) { return; } // Historical/older Agent responses remain readable.
        try {
            boolean model = "model".equals(plan.mode());
            if (!model && !"direct".equals(plan.mode())) { throw new IllegalArgumentException(); }
            if (plan.queries() == null || plan.queries().isEmpty() || plan.queries().size() > (model ? 3 : 1)) {
                throw new IllegalArgumentException();
            }
            if (model) {
                var g=plan.generation();
                if (!bounded(plan.intent(),600) || plan.reason()!=null || g==null
                        || !bounded(g.model(),100) || !bounded(g.host(),253) || !g.host().matches("[a-z0-9.-]+")
                        || !"search-plan-v1".equals(g.promptVersion()) || g.inputHash()==null
                        || !g.inputHash().matches("[a-f0-9]{64}")) { throw new IllegalArgumentException(); }
            } else if (plan.generation()!=null || plan.intent()!=null || plan.reason()==null || !Set.of(
                    "PLANNING_DISABLED","MODEL_DISABLED","MODEL_CONFIG_ERROR","MODEL_BUSY","MODEL_TIMEOUT",
                    "MODEL_UNAVAILABLE","MODEL_INVALID_RESPONSE","MODEL_RATE_LIMITED","MODEL_AUTH_ERROR").contains(plan.reason())) {
                throw new IllegalArgumentException();
            }
            Set<String> evidenceIds = new HashSet<>();
            for (var e : report.evidence()) { evidenceIds.add(e.id()); }
            Set<String> covered = new HashSet<>(), queries = new HashSet<>();
            boolean successful = false;
            for (var q : plan.queries()) {
                if (q==null || !bounded(q.query(),model?200:4000) || !request.language().equals(q.language())
                        || !queries.add(q.query().toLowerCase(java.util.Locale.ROOT))
                        || q.resultCount()<0 || q.resultCount()>5 || q.evidenceIds()==null
                        || q.evidenceIds().size()>q.resultCount() || !evidenceIds.containsAll(q.evidenceIds())
                        || new HashSet<>(q.evidenceIds()).size()!=q.evidenceIds().size()) { throw new IllegalArgumentException(); }
                if (!model && !q.query().equals(request.question().strip())) { throw new IllegalArgumentException(); }
                if ("SUCCEEDED".equals(q.status())) {
                    if(q.errorCode()!=null) { throw new IllegalArgumentException(); }
                    successful=true;
                } else if (!"FAILED".equals(q.status()) || q.resultCount()!=0 || q.errorCode()==null || !Set.of(
                        "SEARCH_TIMEOUT","SEARCH_UNAVAILABLE","SEARCH_INVALID_RESPONSE","SEARCH_RATE_LIMITED").contains(q.errorCode())) {
                    throw new IllegalArgumentException();
                }
                covered.addAll(q.evidenceIds());
            }
            if(!successful || !covered.equals(evidenceIds)) { throw new IllegalArgumentException(); }
        } catch (IllegalArgumentException | NullPointerException exception) {
            throw new AgentException(AgentException.Reason.INVALID_RESPONSE, exception);
        }
    }

    private void validateReport(ResearchReport report) {
        try {
            if (report == null || !bounded(report.answer(), 16000) || !bounded(report.provider(), 80)
                    || !bounded(report.query(), 4000) || report.retrievedAt() == null
                    || report.evidence() == null || report.evidence().size() > 5 || report.sources() == null
                    || report.sources().size() != report.evidence().size()) {
                throw new IllegalArgumentException();
            }
            Set<String> ids = new HashSet<>();
            Set<String> urls = new HashSet<>();
            for (int i = 0; i < report.evidence().size(); i++) {
                var evidence = report.evidence().get(i);
                if (evidence == null || !bounded(evidence.id(), 32) || !evidence.id().matches("E[1-5]")
                        || !ids.add(evidence.id()) || !bounded(evidence.url(), 2048)
                        || !urls.add(evidence.url()) || !evidence.url().equals(report.sources().get(i))
                        || !bounded(evidence.title(), 512) || !bounded(evidence.excerpt(), 1600)
                        || evidence.retrievedAt() == null || evidence.contentHash() == null) {
                    throw new IllegalArgumentException();
                }
                URI uri = URI.create(evidence.url());
                if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null) {
                    throw new IllegalArgumentException();
                }
                String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                        .digest(evidence.excerpt().getBytes(StandardCharsets.UTF_8)));
                if (!hash.equals(evidence.contentHash())) { throw new IllegalArgumentException(); }
            }
            var generation = report.generation();
            if (generation != null) {
                if (!bounded(generation.model(), 100) || !bounded(generation.host(), 253)
                        || !generation.host().matches("[a-z0-9.-]+")
                        || !("evidence-report-v1".equals(generation.promptVersion())
                             || "evidence-report-v2".equals(generation.promptVersion()))
                        || generation.inputHash() == null || !generation.inputHash().matches("[a-f0-9]{64}")
                        || ids.isEmpty()) { throw new IllegalArgumentException(); }
                var citations = java.util.regex.Pattern.compile("\\[([^\\[\\]]+)\\]").matcher(report.answer());
                while (citations.find()) {
                    if (!ids.contains(citations.group(1))) { throw new IllegalArgumentException(); }
                }
            }
        } catch (IllegalArgumentException | NoSuchAlgorithmException exception) {
            throw new AgentException(AgentException.Reason.INVALID_RESPONSE, exception);
        }
    }

    private boolean bounded(String text, int max) {
        return text != null && !text.isBlank() && text.length() <= max;
    }

    private <T> T call(String path, Object request, Class<T> type) {
        try {
            return (type == ResearchReport.class ? researchClient : client).post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(type);
        } catch (RestClientException exception) {
            for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
                if (cause instanceof SocketTimeoutException) {
                    throw new AgentException(AgentException.Reason.TIMEOUT, exception);
                }
            }
            if (exception instanceof ResourceAccessException) {
                throw new AgentException(AgentException.Reason.UNAVAILABLE, exception);
            }
            if (exception instanceof RestClientResponseException upstream) {
                String providerCode = null;
                if (type == ResearchReport.class && upstream.getResponseBodyAsByteArray().length <= 2048) {
                    try {
                        String code = mapper.readTree(upstream.getResponseBodyAsString()).path("code").asText();
                        if (Set.of("SEARCH_TIMEOUT", "SEARCH_UNAVAILABLE", "SEARCH_INVALID_RESPONSE", "SEARCH_RATE_LIMITED",
                                "MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_INVALID_RESPONSE", "MODEL_RATE_LIMITED",
                                "MODEL_AUTH_ERROR", "MODEL_CONFIG_ERROR", "MODEL_INPUT_TOO_LARGE", "MODEL_BUSY").contains(code)) {
                            providerCode = code;
                        }
                    } catch (RuntimeException ignored) { /* Never relay arbitrary upstream errors. */ }
                }
                throw new AgentException(AgentException.Reason.REJECTED, exception, providerCode);
            }
            throw new AgentException(AgentException.Reason.INVALID_RESPONSE, exception);
        }
    }
}
