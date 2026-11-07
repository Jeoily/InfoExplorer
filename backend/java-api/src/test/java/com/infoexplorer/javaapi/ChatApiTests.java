package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.client.AgentClient;
import com.infoexplorer.javaapi.client.AgentException;
import com.infoexplorer.javaapi.dto.ChatRequest;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import tools.jackson.databind.json.JsonMapper;
import com.infoexplorer.javaapi.research.ResearchReport;
import com.infoexplorer.javaapi.research.Evidence;
import java.util.List;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@org.springframework.test.context.ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ChatApiTests {
    @Test void validatesPlanProvenanceBeforeAcceptingAgentResult() {
        var client=new AgentClient("http://127.0.0.1:"+agent.getAddress().getPort(),1000,1000,1000,mapper);
        var valid=ReportFixtures.planned(ReportFixtures.report("report",List.of("https://example.org/evidence")));
        body=mapper.writeValueAsString(valid);
        assertEquals(valid,client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query")));
        for(String broken:List.of(
                body.replace("\"evidenceIds\":[\"E1\"]","\"evidenceIds\":[\"E9\"]"),
                body.replace("\"language\":\"en\"","\"language\":\"zh\""),
                body.replace("\"resultCount\":1","\"resultCount\":0"),
                body.replace("search-plan-v1","unknown-plan"))) {
            body=broken;
            assertEquals(AgentException.Reason.INVALID_RESPONSE,assertThrows(AgentException.class,
                ()->client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).reason());
        }
    }
    static final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
    static final AtomicInteger calls = new AtomicInteger();
    static volatile String body;
    static volatile String received;
    static volatile int status;
    static volatile long delay;
    static final HttpServer agent = startAgent();

    @Value("${local.server.port}") int port;
    @Autowired JsonMapper mapper;
    final HttpClient http = HttpClient.newHttpClient();

    static HttpServer startAgent() {
        try {
            var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.setExecutor(executor);
            server.createContext("/internal/v1/", exchange -> {
                calls.incrementAndGet();
                received = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String responseBody = body;
                int responseStatus = status;
                long responseDelay = delay;
                try {
                    Thread.sleep(responseDelay);
                    byte[] bytes = responseBody.getBytes(StandardCharsets.UTF_8);
                    exchange.getResponseHeaders().set("Content-Type", "application/json");
                    exchange.sendResponseHeaders(responseStatus, bytes.length);
                    exchange.getResponseBody().write(bytes);
                } catch (InterruptedException exception) {
                    Thread.currentThread().interrupt();
                } catch (IOException ignored) {
                    // Expected when the client times out and disconnects.
                } finally {
                    exchange.close();
                }
            });
            server.start();
            return server;
        } catch (IOException exception) {
            throw new ExceptionInInitializerError(exception);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("agent.service.base-url", () -> "http://127.0.0.1:" + agent.getAddress().getPort());
        registry.add("agent.service.read-timeout-ms", () -> 250);
    }

    @BeforeEach
    void reset() {
        body = "{\"answer\":\"upstream answer\",\"sources\":[\"https://example.org/evidence\"]}";
        status = 200;
        delay = 0;
        received = null;
        calls.set(0);
    }

    @AfterAll
    static void close() {
        agent.stop(0);
        executor.shutdownNow();
    }

    HttpResponse<String> ask(String request) throws Exception {
        return http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/chat/ask"))
                .timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(request)).build(), HttpResponse.BodyHandlers.ofString());
    }

    @Test
    void forwardsQuestionAndPreservesAnswerAndSources() throws Exception {
        var response = ask("{\"question\":\"研究开源技术\"}");
        assertEquals(200, response.statusCode());
        assertTrue(response.body().contains("upstream answer"));
        assertTrue(response.body().contains("https://example.org/evidence"));
        assertTrue(received.contains("研究开源技术"));
        assertEquals(1, calls.get());
    }

    @Test
    void rejectsInvalidRequestsWithoutCallingAgent() throws Exception {
        for (String request : new String[]{"{}", "{\"question\":null}", "{\"question\":42}", "{\"question\":true}", "{\"question\":\"  \"}",
                "{", "{\"question\":\"" + "a".repeat(4001) + "\"}",
                "{\"question\":\"" + "😀".repeat(2001) + "\"}"}) {
            var response = ask(request);
            assertEquals(400, response.statusCode());
            assertTrue(response.body().contains("INVALID_REQUEST"));
        }
        assertEquals(0, calls.get());
    }

    @Test
    void acceptsBoundaryLength() throws Exception {
        assertEquals(200, ask("{\"question\":\"" + "a".repeat(4000) + "\"}").statusCode());
    }

    @Test
    void hidesUpstreamErrorContent() throws Exception {
        status = 500;
        body = "{\"detail\":\"private upstream diagnostic\"}";
        var response = ask("{\"question\":\"hello\"}");
        assertEquals(502, response.statusCode());
        assertTrue(response.body().contains("AGENT_ERROR"));
        assertFalse(response.body().contains("private upstream"));
    }

    @Test
    void rejectsMalformedAndIncompleteResponses() throws Exception {
        for (String invalid : new String[]{"not json", "{}", "{\"answer\":\"ok\"}",
                "{\"answer\":\" \",\"sources\":[]}", "{\"answer\":42,\"sources\":[]}",
                "{\"answer\":\"ok\",\"sources\":[42]}", "{\"answer\":\"ok\",\"sources\":[null]}"}) {
            body = invalid;
            var response = ask("{\"question\":\"hello\"}");
            assertEquals(502, response.statusCode());
            assertTrue(response.body().contains("AGENT_INVALID_RESPONSE"));
        }
    }

    @Test
    void timesOutWithoutRetryAndRecoversOnNextRequest() throws Exception {
        delay = 1000;
        var response = ask("{\"question\":\"hello\"}");
        assertEquals(504, response.statusCode());
        assertTrue(response.body().contains("AGENT_TIMEOUT"));
        assertEquals(1, calls.get());
        delay = 0;
        assertEquals(200, ask("{\"question\":\"hello again\"}").statusCode());
    }

    @Test
    void classifiesConnectionFailure() throws Exception {
        int unusedPort;
        try (var socket = new ServerSocket(0)) { unusedPort = socket.getLocalPort(); }
        var client = new AgentClient("http://127.0.0.1:" + unusedPort, 200, 200, 200, mapper);
        var exception = assertThrows(AgentException.class, () -> client.ask(new ChatRequest("hello")));
        assertEquals(AgentException.Reason.UNAVAILABLE, exception.reason());
    }

    @Test
    void validatesEvidenceAndPreservesAllowlistedSearchErrors() {
        var client = new AgentClient("http://127.0.0.1:" + agent.getAddress().getPort(), 1000, 1000, 1000, mapper);
        var report = ReportFixtures.report("[E1] Evidence", List.of("https://example.org/evidence"));
        body = mapper.writeValueAsString(report);
        assertEquals(report, client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query")));
        var item = report.evidence().getFirst();
        var invalid = new Evidence(item.id(), item.url(), item.title(), "tampered", item.retrievedAt(), item.contentHash());
        for (var bad : List.of(
                new ResearchReport(report.answer(), report.sources(), report.provider(), report.query(), report.retrievedAt(), List.of(invalid)),
                new ResearchReport(report.answer(), List.of("https://example.org/different"), report.provider(), report.query(), report.retrievedAt(), report.evidence()),
                new ResearchReport(report.answer(), List.of(item.url(), item.url()), report.provider(), report.query(), report.retrievedAt(), List.of(item, item)))) {
            body = mapper.writeValueAsString(bad);
            assertEquals(AgentException.Reason.INVALID_RESPONSE,
                    assertThrows(AgentException.class, () -> client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).reason());
        }
        status = 502;
        body = "{\"code\":\"SEARCH_RATE_LIMITED\",\"message\":\"private detail\"}";
        assertEquals("SEARCH_RATE_LIMITED", assertThrows(AgentException.class,
                () -> client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).providerCode());
        body = "{\"code\":\"private detail\"}";
        assertNull(assertThrows(AgentException.class, () -> client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).providerCode());
    }

    @Test
    void validatesGenerationMetadataAndCitations() {
        var client = new AgentClient("http://127.0.0.1:" + agent.getAddress().getPort(), 1000, 1000, 1000, mapper);
        var report = ReportFixtures.report("Claim [E1]", List.of("https://example.org/evidence"));
        var metadata = new com.infoexplorer.javaapi.research.Generation("fixture-model", "models.example.org", "evidence-report-v1", "a".repeat(64));
        var generated = new ResearchReport(report.answer(), report.sources(), report.provider(), report.query(), report.retrievedAt(), report.evidence(), metadata);
        body = mapper.writeValueAsString(generated);
        assertEquals(generated, client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query")));
        body = mapper.writeValueAsString(new ResearchReport("Claim [E9]", report.sources(), report.provider(), report.query(), report.retrievedAt(), report.evidence(), metadata));
        assertEquals(AgentException.Reason.INVALID_RESPONSE, assertThrows(AgentException.class,
                () -> client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).reason());
        for (String code : List.of("MODEL_TIMEOUT", "MODEL_RATE_LIMITED", "MODEL_INVALID_RESPONSE", "MODEL_AUTH_ERROR", "MODEL_CONFIG_ERROR", "MODEL_BUSY")) {
            status = 502;
            body = "{\"code\":\"" + code + "\",\"message\":\"private provider diagnostic\"}";
            assertEquals(code, assertThrows(AgentException.class, () -> client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query"))).providerCode());
        }
    }

    @Test
    void researchHasAnIndependentReadTimeout() {
        var client = new AgentClient("http://127.0.0.1:" + agent.getAddress().getPort(), 1000, 50, 1000, mapper);
        body = mapper.writeValueAsString(ReportFixtures.report("retrieved", List.of()));
        delay = 250;
        assertEquals("retrieved", client.research(new com.infoexplorer.javaapi.dto.ResearchRequest("query")).answer());
        assertEquals(AgentException.Reason.TIMEOUT,
                assertThrows(AgentException.class, () -> client.ask(new ChatRequest("query"))).reason());
    }
}
