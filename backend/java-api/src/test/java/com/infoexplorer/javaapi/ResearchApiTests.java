package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.client.AgentClient;
import com.infoexplorer.javaapi.client.AgentException;

import com.infoexplorer.javaapi.research.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import tools.jackson.databind.json.JsonMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ResearchApiTests {
    @Value("${local.server.port}") int port;
    @Autowired JdbcTemplate jdbc;
    @Autowired JsonMapper mapper;
    @Autowired ResearchRepository repository;
    @Autowired ResearchExecutor runner;
    @MockitoBean AgentClient agent;
    @MockitoBean com.infoexplorer.javaapi.client.WebAgentClient controlledAgent;
    final HttpClient http = HttpClient.newHttpClient();

    @BeforeEach
    void clear() {
        jdbc.update("DELETE FROM research_evidence");
        jdbc.update("DELETE FROM research_execution_control");
        jdbc.update("DELETE FROM research_run");
        jdbc.update("DELETE FROM research_task");
        reset(agent);
        reset(controlledAgent);
        when(controlledAgent.wikiControlled(any(),any(),any(),any())).thenAnswer(call ->
            agent.research(new com.infoexplorer.javaapi.dto.ResearchRequest(call.getArgument(1),call.getArgument(2))));
    }

    HttpResponse<String> post(String body, String key) throws Exception {
        var request = HttpRequest.newBuilder(URI.create(base()))
                .timeout(Duration.ofSeconds(5)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body));
        if (key != null) { request.header("Idempotency-Key", key); }
        return http.send(request.build(), HttpResponse.BodyHandlers.ofString());
    }

    HttpResponse<String> get(String id) throws Exception {
        return http.send(HttpRequest.newBuilder(URI.create(base() + "/" + id))
                .timeout(Duration.ofSeconds(5)).GET().build(), HttpResponse.BodyHandlers.ofString());
    }

    String base() { return "http://127.0.0.1:" + port + "/api/v1/research-tasks"; }
    HttpResponse<String> retry(String id, String body) throws Exception {
        return http.send(HttpRequest.newBuilder(URI.create(base() + "/" + id + "/retry"))
                .timeout(Duration.ofSeconds(5)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body)).build(), HttpResponse.BodyHandlers.ofString());
    }

    @Test void concurrentRetriesAndLateResultsPreserveHistory() throws Exception {
        RetryChecks.concurrencyAndHistory(repository);
        verifyNoInteractions(agent);
    }

    @Test void manualRetryHasExecutionCap() { RetryChecks.cap(repository); }

    @Test void requestLanguageIsValidatedPersistedAndPartOfIdempotency() throws Exception {
        var response=post("{\"question\":\"软件工程\",\"language\":\"zh\"}","language-key");
        assertEquals(202,response.statusCode());
        var task=mapper.readValue(response.body(),ResearchTask.class);
        assertEquals("zh",task.language());
        assertEquals(task.id(),mapper.readValue(post("{\"question\":\"软件工程\",\"language\":\"zh\"}","language-key").body(),ResearchTask.class).id());
        assertEquals(409,post("{\"question\":\"软件工程\",\"language\":\"en\"}","language-key").statusCode());
        for(String language: List.of("ZH","fr","","https://example.org"))
            assertEquals(400,post("{\"question\":\"topic\",\"language\":\""+language+"\"}",null).statusCode());
        when(agent.research(any())).thenThrow(new AgentException(AgentException.Reason.REJECTED,null,"SEARCH_TIMEOUT"));
        runner.runNext();
        var failed=repository.find(task.id()).orElseThrow();
        repository.retry(task.id(),failed.runId());runner.runNext();
        verify(agent,times(2)).research(new com.infoexplorer.javaapi.dto.ResearchRequest("软件工程","zh"));
        assertEquals("zh",repository.find(task.id()).orElseThrow().language());
        assertEquals("en",mapper.readValue(post("{\"question\":\"default\"}",null).body(),ResearchTask.class).language());
    }

    @Test void retryTransitionAndAcceptedFlagRollbackTogether() {
        var task = repository.create("rollback retry", null);
        var run = repository.claimNext().orElseThrow();
        repository.fail(run, "MODEL_TIMEOUT");
        jdbc.execute("ALTER TABLE research_task ADD CONSTRAINT test_reject_retry CHECK(attempt_no=1)");
        try {
            assertThrows(org.springframework.dao.DataAccessException.class, () -> repository.retry(task.id(), run.runId()));
            assertFalse(repository.history(task.id()).getFirst().retryAccepted());
            assertEquals(ResearchTask.Status.FAILED, repository.find(task.id()).orElseThrow().status());
        } finally { jdbc.execute("ALTER TABLE research_task DROP CONSTRAINT test_reject_retry"); }
    }

    @Test void retryHttpLifecycleAndHistory() throws Exception {
        var task = repository.create("retry public example", "retry-create");
        when(agent.research(any())).thenThrow(new AgentException(AgentException.Reason.REJECTED, null, "MODEL_TIMEOUT"))
                .thenReturn(ReportFixtures.report("ok", List.of("https://example.org/evidence")));
        runner.runNext();
        var failed = task(get(task.id()));
        String body = "{\"failedRunId\":\"" + failed.runId() + "\"}";
        var queued = retry(task.id(), body);
        assertEquals(202, queued.statusCode());
        assertTrue(queued.headers().firstValue("Location").orElseThrow().endsWith(task.id()));
        assertEquals(ResearchTask.Status.PENDING, task(queued).status());
        assertEquals(202, retry(task.id(), body).statusCode());
        assertTrue(runner.runNext()); assertFalse(runner.runNext());
        assertEquals(ResearchTask.Status.SUCCEEDED, task(get(task.id())).status());
        assertEquals(202, retry(task.id(), body).statusCode());
        assertEquals(2, mapper.readTree(get(task.id() + "/runs").body()).size());
        assertEquals(task.id(), task(post("{\"question\":\"retry public example\"}", "retry-create")).id());
        verify(agent, times(2)).research(any());
    }

    @Test void retryRejectsInvalidMissingForeignAndNonFailedRuns() throws Exception {
        var a = repository.create("one", null);
        var claim = repository.claimNext().orElseThrow();
        String body = "{\"failedRunId\":\"" + claim.runId() + "\"}";
        assertEquals(409, retry(a.id(), body).statusCode());
        for (String invalid : List.of("{}", "null", "{", "{\"failedRunId\":12}", "{\"failedRunId\":\"wrong\"}")) {
            assertEquals(400, retry(a.id(), invalid).statusCode());
        }
        assertEquals(400, retry("invalid", body).statusCode());
        assertEquals(404, retry(UUID.randomUUID().toString(), body).statusCode());
        repository.fail(claim, "MODEL_TIMEOUT");
        var b = repository.create("two", null);
        assertEquals(409, retry(b.id(), body).statusCode());
        assertEquals(404, get(UUID.randomUUID() + "/runs").statusCode());
        assertEquals(0, mapper.readTree(get(b.id() + "/runs").body()).size());
        verifyNoInteractions(agent);
    }
    ResearchTask task(HttpResponse<String> response) { return mapper.readValue(response.body(), ResearchTask.class); }

    @Test
    void createsAndQueriesDurablePendingTaskBeforeAgentCall() throws Exception {
        var response = post("{\"question\":\"研究技术演进\"}", "first-request");
        assertEquals(202, response.statusCode());
        var task = task(response);
        assertEquals(ResearchTask.Status.PENDING, task.status());
        assertTrue(response.headers().firstValue("Location").orElseThrow().endsWith(task.id()));
        assertEquals(task, task(get(task.id())));
        assertNull(task.result());
        assertNull(task.runId());
        assertNotNull(task.createdAt());
        verifyNoInteractions(agent);
    }

    @Test
    void persistsResultAndSourcesAndDoesNotRunCompletedTaskAgain() throws Exception {
        var created = task(post("{\"question\":\"SQL ' 引号\"}", null));
        var answer = ReportFixtures.report("资料汇总", List.of("https://example.org/a?q=中文", "https://example.org/b"));
        when(agent.research(any())).thenReturn(answer);
        assertTrue(runner.runNext());
        var completed = task(get(created.id()));
        assertEquals(ResearchTask.Status.SUCCEEDED, completed.status());
        assertEquals(answer, completed.result());
        assertNotNull(completed.runId());
        assertNotNull(completed.startedAt());
        assertNotNull(completed.completedAt());
        assertNull(completed.errorCode());
        assertFalse(runner.runNext());
        verify(agent, times(1)).research(any());
    }

    @Test
    void slowExecutionDoesNotBlockTaskQueriesOrNewSubmissions() throws Exception {
        var created = task(post("{\"question\":\"slow\"}", null));
        var started = new CountDownLatch(1);
        var release = new CountDownLatch(1);
        when(agent.research(any())).thenAnswer(invocation -> {
            started.countDown();
            if (!release.await(5, TimeUnit.SECONDS)) { throw new IllegalStateException("Test did not release Agent"); }
            return ReportFixtures.report("done", List.of());
        });
        try (var pool = Executors.newSingleThreadExecutor()) {
            var execution = pool.submit(runner::runNext);
            try {
                assertTrue(started.await(5, TimeUnit.SECONDS));
                assertEquals(ResearchTask.Status.RUNNING, task(get(created.id())).status());
                assertEquals(202, post("{\"question\":\"another task\"}", null).statusCode());
            } finally {
                release.countDown();
            }
            assertTrue(execution.get(5, TimeUnit.SECONDS));
        }
        assertEquals(ResearchTask.Status.SUCCEEDED, task(get(created.id())).status());
    }

    @ParameterizedTest
    @EnumSource(AgentException.Reason.class)
    void savesSafeFailureWithoutAutomaticRetry(AgentException.Reason reason) throws Exception {
        var created = task(post("{\"question\":\"test\"}", null));
        when(agent.research(any())).thenThrow(new AgentException(reason, new RuntimeException("private details")));
        runner.runNext();
        var response = get(created.id());
        var failed = task(response);
        assertEquals(200, response.statusCode());
        assertEquals(ResearchTask.Status.FAILED, failed.status());
        assertEquals(switch (reason) {
            case TIMEOUT -> "AGENT_TIMEOUT";
            case UNAVAILABLE -> "AGENT_UNAVAILABLE";
            case REJECTED -> "AGENT_ERROR";
            case INVALID_RESPONSE -> "AGENT_INVALID_RESPONSE";
        }, failed.errorCode());
        assertNull(failed.result());
        assertNotNull(failed.completedAt());
        assertFalse(response.body().contains("private details"));
        assertFalse(runner.runNext());
        verify(agent, times(1)).research(any());
    }

    @Test
    void replaysSameKeyAndRejectsConflictingQuestion() throws Exception {
        var first = task(post("{\"question\":\"one\"}", "same-key"));
        var replay = task(post("{\"question\":\"one\"}", "same-key"));
        assertEquals(first.id(), replay.id());
        assertEquals(409, post("{\"question\":\"two\"}", "same-key").statusCode());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM research_task", Integer.class));
    }

    @Test
    void concurrentSameKeyCreatesExactlyOneTask() throws Exception {
        try (var pool = Executors.newFixedThreadPool(8)) {
            List<Callable<HttpResponse<String>>> calls = IntStream.range(0, 8)
                    .mapToObj(i -> (Callable<HttpResponse<String>>) () -> post("{\"question\":\"same\"}", "concurrent-key")).toList();
            var responses = pool.invokeAll(calls);
            String id = null;
            for (var response : responses) {
                var value = response.get();
                assertEquals(202, value.statusCode());
                if (id == null) { id = task(value).id(); }
                assertEquals(id, task(value).id());
            }
        }
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM research_task", Integer.class));
    }

    @Test
    void onlyOneWorkerCanClaimAndLateCompletionCannotOverwriteRecovery() throws Exception {
        var created = task(post("{\"question\":\"race\"}", null));
        ResearchRepository.Claim winner = null;
        int winners = 0;
        try (var pool = Executors.newFixedThreadPool(8)) {
            var results = pool.invokeAll(IntStream.range(0, 8)
                    .mapToObj(i -> (Callable<java.util.Optional<ResearchRepository.Claim>>) repository::claimNext).toList());
            for (var result : results) {
                if (result.get().isPresent()) { winners++; winner = result.get().get(); }
            }
        }
        assertEquals(1, winners);
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
        assertEquals(1, repository.recoverInterrupted());
        var stale = winner;
        assertThrows(IllegalStateException.class, () -> repository.succeed(stale, ReportFixtures.report("late", List.of())));
        var failed = task(get(created.id()));
        assertEquals(ResearchTask.Status.FAILED, failed.status());
        assertEquals("EXECUTION_INTERRUPTED", failed.errorCode());
        assertNull(failed.result());
    }

    @Test
    void validatesInputsAndHandlesMissingIds() throws Exception {
        for (String invalid : List.of("{}", "{", "{\"question\":\" \"}", "{\"question\":42}",
                "{\"question\":\"" + "a".repeat(4001) + "\"}")) {
            assertEquals(400, post(invalid, null).statusCode());
        }
        assertEquals(400, post("{\"question\":\"ok\"}", "invalid key").statusCode());
        assertEquals(400, post("{\"question\":\"ok\"}", "a".repeat(129)).statusCode());
        assertEquals(400, get("invalid-id").statusCode());
        assertEquals(404, get(UUID.randomUUID().toString()).statusCode());
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM research_task", Integer.class));
        verifyNoInteractions(agent);
    }

    @Test
    void evidenceInsertionFailureRollsBackResultAndTaskStatus() {
        var created = repository.create("atomic", null);
        var claim = repository.claimNext().orElseThrow();
        var valid = ReportFixtures.report("answer", List.of("https://example.org/evidence"));
        var item = valid.evidence().getFirst();
        var duplicate = new ResearchReport(valid.answer(), valid.sources(), valid.provider(), valid.query(), valid.retrievedAt(), List.of(item, item));
        assertThrows(org.springframework.dao.DataAccessException.class, () -> repository.succeed(claim, duplicate));
        assertEquals(ResearchTask.Status.RUNNING, repository.find(created.id()).orElseThrow().status());
        assertNull(repository.find(created.id()).orElseThrow().result());
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM research_evidence", Integer.class));
    }

    @Test
    void persistsSearchFailureCode() throws Exception {
        var task = task(post("{\"question\":\"search\"}", null));
        when(agent.research(any())).thenThrow(new AgentException(AgentException.Reason.REJECTED, null, "SEARCH_TIMEOUT"));
        runner.runNext();
        assertEquals("SEARCH_TIMEOUT", task(get(task.id())).errorCode());
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM research_evidence", Integer.class));
    }
}

