package com.infoexplorer.javaapi;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import com.infoexplorer.javaapi.research.ResearchExecutor;
import com.infoexplorer.javaapi.research.ResearchTask;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_URL", matches = "http://127\\.0\\.0\\.1:[0-9]+")
@org.springframework.test.context.ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class RealAgentIntegrationTests {
    @Test
    @EnabledIfEnvironmentVariable(named="INFOEXPLORER_TEST_AGENT_MODE",matches="offline")
    void plannedSearchCrossesRealHttpAndPersistsProvenance() throws Exception {
        var http=HttpClient.newHttpClient();
        String base="http://127.0.0.1:"+port+"/api/v1/research-tasks";
        var response=http.send(HttpRequest.newBuilder(URI.create(base)).header("Content-Type","application/json")
            .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"PLAN_FIXTURE\",\"language\":\"zh\"}")).build(),HttpResponse.BodyHandlers.ofString());
        assertEquals(202,response.statusCode());
        var created=mapper.readValue(response.body(),ResearchTask.class);runner.runNext();
        var read=http.send(HttpRequest.newBuilder(URI.create(base+"/"+created.id())).GET().build(),HttpResponse.BodyHandlers.ofString());
        var done=mapper.readValue(read.body(),ResearchTask.class);
        assertEquals(ResearchTask.Status.SUCCEEDED,done.status(),done.errorCode());
        assertEquals("model",done.result().plan().mode());
        assertEquals(2,done.result().plan().queries().size());
        assertEquals(1,done.result().evidence().size());
        for(var q:done.result().plan().queries()) {
            assertEquals("zh",q.language());assertEquals(java.util.List.of("E1"),q.evidenceIds());
        }
    }
    @Test
    @EnabledIfEnvironmentVariable(named="INFOEXPLORER_TEST_AGENT_MODE",matches="offline")
    void languageAndEmptyResultsCrossRealHttp() throws Exception {
        var http=HttpClient.newHttpClient();
        String base="http://127.0.0.1:"+port+"/api/v1/research-tasks";
        for(String language:java.util.List.of("en","zh")) {
            for(String question:java.util.List.of("public topic","EMPTY_RESULT")) {
                var request=HttpRequest.newBuilder(URI.create(base)).header("Content-Type","application/json")
                    .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\""+question+"\",\"language\":\""+language+"\"}")).build();
                var accepted=http.send(request,HttpResponse.BodyHandlers.ofString());assertEquals(202,accepted.statusCode());
                var created=mapper.readValue(accepted.body(),ResearchTask.class);runner.runNext();
                var response=http.send(HttpRequest.newBuilder(URI.create(base+"/"+created.id())).GET().build(),HttpResponse.BodyHandlers.ofString());
                var done=mapper.readValue(response.body(),ResearchTask.class);
                assertEquals(ResearchTask.Status.SUCCEEDED,done.status());assertEquals(language,done.language());
                assertEquals("wikipedia-"+language,done.result().provider());
                assertEquals(question.equals("EMPTY_RESULT"),done.result().evidence().isEmpty());
            }
        }
    }
    @Value("${local.server.port}") int port;
    @Autowired ResearchExecutor runner;
    @Autowired JsonMapper mapper;

    @Test
    void researchTaskPersistsActualPythonResult() throws Exception {
        var http = HttpClient.newHttpClient();
        String url = "http://127.0.0.1:" + port + "/api/v1/research-tasks";
        var create = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"artificial intelligence\"}")).build();
        var accepted = http.send(create, HttpResponse.BodyHandlers.ofString());
        assertEquals(202, accepted.statusCode());
        var task = mapper.readValue(accepted.body(), ResearchTask.class);
        assertEquals(ResearchTask.Status.PENDING, task.status());
        assertTrue(runner.runNext());
        var response = http.send(HttpRequest.newBuilder(URI.create(url + "/" + task.id()))
                .timeout(Duration.ofSeconds(5)).GET().build(), HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        var completed = mapper.readValue(response.body(), ResearchTask.class);
        assertEquals(ResearchTask.Status.SUCCEEDED, completed.status(), completed.errorCode());
        assertEquals("wikipedia-en", completed.result().provider());
        assertFalse(completed.result().evidence().isEmpty());
        assertEquals(completed.result().sources().size(), completed.result().evidence().size());
        assertNotNull(completed.result().evidence().getFirst().contentHash());
        if ("offline".equals(System.getenv("INFOEXPLORER_TEST_AGENT_MODE"))) {
            assertNotNull(completed.result().generation());
            assertEquals("fixture-model", completed.result().generation().model());
            assertTrue(completed.result().answer().contains("[E1]"));
        }
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_MODE", matches = "offline")
    void persistsSafePythonModelFailures() throws Exception {
        var http = HttpClient.newHttpClient();
        String url = "http://127.0.0.1:" + port + "/api/v1/research-tasks";
        for (String code : java.util.List.of("MODEL_TIMEOUT", "MODEL_RATE_LIMITED", "MODEL_INVALID_RESPONSE")) {
            var accepted = http.send(HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(5)).header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"" + code + "\"}")).build(), HttpResponse.BodyHandlers.ofString());
            assertEquals(202, accepted.statusCode());
            var task = mapper.readValue(accepted.body(), ResearchTask.class);
            assertTrue(runner.runNext());
            var response = http.send(HttpRequest.newBuilder(URI.create(url + "/" + task.id()))
                    .timeout(Duration.ofSeconds(5)).GET().build(), HttpResponse.BodyHandlers.ofString());
            var completed = mapper.readValue(response.body(), ResearchTask.class);
            assertEquals(ResearchTask.Status.FAILED, completed.status());
            assertEquals(code, completed.errorCode());
            assertNull(completed.result());
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("agent.service.base-url", () -> System.getenv("INFOEXPLORER_TEST_AGENT_URL"));
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_MODE", matches = "offline")
    void manualRetryThroughActualPythonHttpPreservesBothExecutions() throws Exception {
        var http = HttpClient.newHttpClient();
        String base = "http://127.0.0.1:" + port + "/api/v1/research-tasks";
        var accepted = http.send(HttpRequest.newBuilder(URI.create(base)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"RETRY_ONCE\"}")).build(), HttpResponse.BodyHandlers.ofString());
        assertEquals(202, accepted.statusCode());
        var task = mapper.readValue(accepted.body(), ResearchTask.class);
        assertTrue(runner.runNext());
        var fetch = HttpRequest.newBuilder(URI.create(base + "/" + task.id())).GET().build();
        var failed = mapper.readValue(http.send(fetch, HttpResponse.BodyHandlers.ofString()).body(), ResearchTask.class);
        assertEquals("MODEL_TIMEOUT", failed.errorCode());
        var retry = HttpRequest.newBuilder(URI.create(base + "/" + task.id() + "/retry"))
                .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(
                        "{\"failedRunId\":\"" + failed.runId() + "\"}")).build();
        assertEquals(202, http.send(retry, HttpResponse.BodyHandlers.ofString()).statusCode());
        assertEquals(202, http.send(retry, HttpResponse.BodyHandlers.ofString()).statusCode());
        assertTrue(runner.runNext()); assertFalse(runner.runNext());
        var completed = mapper.readValue(http.send(fetch, HttpResponse.BodyHandlers.ofString()).body(), ResearchTask.class);
        assertEquals(ResearchTask.Status.SUCCEEDED, completed.status());
        assertEquals("fixture-model", completed.result().generation().model());
        assertFalse(completed.result().evidence().isEmpty());
        var history = mapper.readTree(http.send(HttpRequest.newBuilder(URI.create(base + "/" + task.id() + "/runs"))
                .GET().build(), HttpResponse.BodyHandlers.ofString()).body());
        assertEquals(2, history.size());
        assertEquals("MODEL_TIMEOUT", history.get(0).get("errorCode").asText());
        assertEquals("SUCCEEDED", history.get(1).get("status").asText());
    }

    @Test
    void javaCallsActualPythonService() throws Exception {
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/chat/ask"))
                .timeout(Duration.ofSeconds(15)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"integration-check\"}")).build();
        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        assertTrue(response.body().contains("Python Agent received: integration-check"));
        assertTrue(response.body().contains("\"sources\":[]"));
    }
}
