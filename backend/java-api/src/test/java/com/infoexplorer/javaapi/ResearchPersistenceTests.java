package com.infoexplorer.javaapi;


import com.infoexplorer.javaapi.research.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;

import java.net.ServerSocket;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ResearchPersistenceTests {
    @TempDir Path directory;

    @Test void upgradesLanguageWithoutRewritingReports() {
        String url="jdbc:h2:file:"+directory.resolve("research").toString().replace('\\','/')+";DB_CLOSE_ON_EXIT=FALSE";
        String en,zh;
        try(var old=new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
                "--spring.profiles.active=test","--spring.datasource.url="+url,"--spring.flyway.target=5","--research.worker.enabled=false")) {
            var jdbc=old.getBean(JdbcTemplate.class);
            en=LanguageMigrationChecks.seed(jdbc,"en"); zh=LanguageMigrationChecks.seed(jdbc,"zh");
        }
        try(var updated=open(false,9)) {
            LanguageMigrationChecks.verify(updated.getBean(ResearchRepository.class),updated.getBean(JdbcTemplate.class),en,zh);
        }
    }

    ConfigurableApplicationContext open(boolean worker, int agentPort) {
        return new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
                "--spring.profiles.active=test",
                "--spring.datasource.url=jdbc:h2:file:" + directory.resolve("research").toString().replace('\\', '/') + ";DB_CLOSE_ON_EXIT=FALSE",
                "--research.worker.enabled=" + worker,
                "--research.worker.poll-delay-ms=50",
                "--agent.service.base-url=http://127.0.0.1:" + agentPort,
                "--agent.service.connect-timeout-ms=200",
                "--agent.service.read-timeout-ms=200",
                "--spring.main.banner-mode=off");
    }

    @Test
    void upgradesV1DatabaseWithoutFabricatingEvidenceForOldResults() {
        String url = "jdbc:h2:file:" + directory.resolve("research").toString().replace('\\', '/') + ";DB_CLOSE_ON_EXIT=FALSE";
        String taskId = java.util.UUID.randomUUID().toString();
        try (var old = new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
                "--spring.profiles.active=test", "--spring.datasource.url=" + url,
                "--spring.flyway.target=1", "--research.worker.enabled=false", "--spring.main.banner-mode=off")) {
            var jdbc = old.getBean(JdbcTemplate.class);
            jdbc.update("INSERT INTO research_task(id, question, status, created_at, updated_at) VALUES (?, 'old question', 'SUCCEEDED', 1, 2)", taskId);
            jdbc.update("INSERT INTO research_run(id, task_id, status, started_at, completed_at, answer, sources_json) VALUES (?, ?, 'SUCCEEDED', 1, 2, 'old answer', '[]')",
                    java.util.UUID.randomUUID().toString(), taskId);
        }
        try (var updated = open(false, 9)) {
            var result = updated.getBean(ResearchRepository.class).find(taskId).orElseThrow().result();
            assertEquals("old answer", result.answer());
            assertEquals("legacy-mock", result.provider());
            assertNull(result.retrievedAt());
            assertTrue(result.evidence().isEmpty());
        }
    }

    @Test
    void reopensFileDatabaseAndRecoversInterruptedAndQueuedTasks() throws Exception {
        int unusedPort;
        try (var socket = new ServerSocket(0)) { unusedPort = socket.getLocalPort(); }
        String completedId;
        String interruptedId;
        String pendingId;
        var base = ReportFixtures.report("saved result [E1]", List.of("https://example.org/evidence"));
        var expected = ReportFixtures.planned(new ResearchReport(base.answer(), base.sources(), base.provider(), base.query(), base.retrievedAt(),
                base.evidence(), new Generation("fixture-model", "models.example.org", "evidence-report-v1", "a".repeat(64))));
        try (var first = open(false, unusedPort)) {
            var store = first.getBean(ResearchRepository.class);
            completedId = store.create("completed", "persistent-key").id();
            store.succeed(store.claimNext().orElseThrow(), expected);
            interruptedId = store.create("interrupted", null).id();
            store.claimNext().orElseThrow();
            pendingId = store.create("pending", null).id();
        }
        try (var second = open(true, unusedPort)) {
            var store = second.getBean(ResearchRepository.class);
            assertEquals(expected, store.find(completedId).orElseThrow().result());
            assertEquals(completedId, second.getBean(ResearchService.class).create("completed", "persistent-key").id());
            var interrupted = store.find(interruptedId).orElseThrow();
            assertEquals(ResearchTask.Status.FAILED, interrupted.status());
            assertEquals("EXECUTION_INTERRUPTED", interrupted.errorCode());
            long deadline = System.nanoTime() + Duration.ofSeconds(5).toNanos();
            while (store.find(pendingId).orElseThrow().status() != ResearchTask.Status.FAILED && System.nanoTime() < deadline) {
                Thread.sleep(20);
            }
            // The pending task was actually resumed by the worker and attempted the unavailable Agent.
            assertEquals("AGENT_UNAVAILABLE", store.find(pendingId).orElseThrow().errorCode());
            assertEquals(3, second.getBean(JdbcTemplate.class).queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
            assertEquals(1, second.getBean(JdbcTemplate.class).queryForObject(
                    "SELECT COUNT(*) FROM \"flyway_schema_history\" WHERE \"success\" = TRUE AND \"version\" = '1'", Integer.class));
        }
    }

    @Test void upgradesFailedRunAndPreservesRetryAcrossReopen() {
        String url = "jdbc:h2:file:" + directory.resolve("research").toString().replace('\\', '/') + ";DB_CLOSE_ON_EXIT=FALSE";
        String taskId = java.util.UUID.randomUUID().toString(), runId = java.util.UUID.randomUUID().toString();
        try (var legacy = new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
                "--spring.profiles.active=test", "--spring.datasource.url=" + url,
                "--spring.flyway.target=4", "--research.worker.enabled=false", "--spring.main.banner-mode=off")) {
            var jdbc = legacy.getBean(JdbcTemplate.class);
            jdbc.update("INSERT INTO research_task(id,question,status,created_at,updated_at) VALUES (?,'legacy failed','FAILED',1,2)", taskId);
            jdbc.update("INSERT INTO research_run(id,task_id,status,started_at,completed_at,error_code) VALUES (?,?,'FAILED',1,2,'MODEL_TIMEOUT')", runId, taskId);
        }
        try (var migrated = open(false, 9)) {
            var store = migrated.getBean(ResearchRepository.class);
            assertEquals(runId, store.find(taskId).orElseThrow().runId());
            store.retry(taskId, runId);
        }
        String secondRun;
        try (var reopened = open(false, 9)) {
            var store = reopened.getBean(ResearchRepository.class);
            assertEquals(ResearchTask.Status.PENDING, store.find(taskId).orElseThrow().status());
            assertTrue(store.history(taskId).getFirst().retryAccepted());
            var claim = store.claimNext().orElseThrow();
            secondRun = claim.runId();
        }
        try (var recovered = open(true, 9)) {
            var store = recovered.getBean(ResearchRepository.class);
            // Application startup recovers an interrupted second execution, retaining the first failure.
            assertEquals("EXECUTION_INTERRUPTED", store.find(taskId).orElseThrow().errorCode());
            assertEquals("MODEL_TIMEOUT", store.history(taskId).getFirst().errorCode());
            assertEquals(2, store.history(taskId).size());
        }
        try (var manual = open(false, 9)) {
            var store = manual.getBean(ResearchRepository.class);
            store.retry(taskId, secondRun);
            store.succeed(store.claimNext().orElseThrow(), ReportFixtures.report("recovered", List.of()));
        }
        try (var finalOpen = open(false, 9)) {
            var store = finalOpen.getBean(ResearchRepository.class);
            assertEquals(ResearchTask.Status.SUCCEEDED, store.find(taskId).orElseThrow().status());
            assertEquals(3, store.history(taskId).size());
        }
    }
}

