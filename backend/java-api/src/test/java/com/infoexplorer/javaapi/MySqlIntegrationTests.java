package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.DriverManager;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.*;

/** Real MySQL only; each test owns one freshly created, random schema. Never cleans a supplied database. */
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_MYSQL_TEST", matches = "1")
class MySqlIntegrationTests {
    final String schema = "infoexplorer_test_" + UUID.randomUUID().toString().replace("-", "");
    boolean created;
    ConfigurableApplicationContext context;

    String url(String database) {
        String port = System.getenv().getOrDefault("MYSQL_PORT", "3306");
        if (!port.matches("[0-9]{1,5}")) throw new IllegalArgumentException("Invalid local MySQL port");
        return "jdbc:mysql://127.0.0.1:" + port + "/" + database
                + "?sslMode=REQUIRED&connectionTimeZone=UTC&characterEncoding=UTF-8&connectTimeout=5000&socketTimeout=15000";
    }

    java.sql.Connection admin() throws Exception {
        return DriverManager.getConnection(url(""), System.getenv("MYSQL_USER"), System.getenv("MYSQL_PASSWORD"));
    }

    ConfigurableApplicationContext open() {
        return openVersion("latest");
    }

    ConfigurableApplicationContext openVersion(String version) {
        return new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
                "--spring.profiles.active=mysql", "--spring.datasource.url=" + url(schema),
                "--spring.flyway.target=" + version,
                "--research.worker.enabled=false", "--spring.main.banner-mode=off");
    }

    @BeforeEach
    void prepare(TestInfo info) throws Exception {
        try (var connection = admin(); var statement = connection.createStatement()) {
            statement.executeUpdate("CREATE DATABASE `" + schema + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin");
            created = true;
        }
        String method=info.getTestMethod().orElseThrow().getName();
        context = method.equals("upgradesExecutionControlFromV8") ? openVersion("8") : method.equals("upgradeTrackingAndRestart") ? openVersion("7") : method.equals("upgradesModelSessionFromV6") ? openVersion("6") : method.equals("upgradesExistingRunsForRetry") ? openVersion("2") : method.equals("upgradesLanguageWithoutRewritingReports") ? openVersion("3") : method.equals("upgradesPlanKeepingOldReport") ? openVersion("4") : open();
    }

    @AfterEach
    void cleanup() throws Exception {
        if (context != null) context.close();
        if (created && schema.matches("infoexplorer_test_[a-f0-9]{32}")) {
            try (var connection = admin(); var statement = connection.createStatement()) {
                statement.executeUpdate("DROP DATABASE `" + schema + "`");
            }
        }
    }

    @Test
    void migrationEnforcesConstraintsAndCaseSensitiveKeys() {
        var store = context.getBean(ResearchRepository.class);
        var jdbc = context.getBean(JdbcTemplate.class);
        assertTrue(jdbc.queryForObject("SELECT VERSION()", String.class).startsWith("8.4."));
        var first = store.create("中文 😀", "Request-A");
        var second = store.create("中文 😀", "request-a");
        assertNotEquals(first.id(), second.id());
        assertEquals("中文 😀", store.find(first.id()).orElseThrow().question());
        assertThrows(DataAccessException.class, () -> jdbc.update(
                "INSERT INTO research_run(id, task_id, status, started_at) VALUES (?, ?, 'RUNNING', 1)", UUID.randomUUID().toString(), UUID.randomUUID().toString()));
        assertThrows(DataAccessException.class, () -> jdbc.update("UPDATE research_task SET status='INVALID' WHERE id=?", first.id()));
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='research_task' AND index_name='idx_research_task_pending' AND seq_in_index=1", Integer.class));
        assertEquals(9, jdbc.queryForObject("SELECT COUNT(*) FROM flyway_schema_history WHERE success=1", Integer.class));
    }

    @Test void trackingLifecycle() throws Exception { TrackingChecks.lifecycle(context); }
    @Test void executionControlLifecycle() { ExecutionChecks.lifecycle(context.getBean(ResearchRepository.class)); }
    @Test void upgradesExecutionControlFromV8() {
        String task=context.getBean(ResearchRepository.class).create("existing task",null).id();
        context.close();context=open();
        var repo=context.getBean(ResearchRepository.class);
        assertEquals("queued",repo.progress(task).stage());
        var claim=repo.claimNext().orElseThrow();
        repo.cancel(task,claim.runId());repo.recoverInterrupted();
        assertEquals("EXECUTION_CANCELLED",repo.find(task).orElseThrow().errorCode());
    }
    @Test void trackingScheduleRecovery() { TrackingChecks.scheduler(context); }
    @Test void trackingChanges() { TrackingChecks.changes(context); }
    @Test void upgradeTrackingAndRestart() {
        var research=context.getBean(ResearchRepository.class);
        String task=research.create("Existing public research","before-tracking").id();
        context.close(); context=open();
        assertEquals("Existing public research",context.getBean(ResearchRepository.class).find(task).orElseThrow().question());
        var tracking=context.getBean(com.infoexplorer.javaapi.tracking.TrackingRepository.class);
        var topic=tracking.create(new com.infoexplorer.javaapi.tracking.TrackingModels.Config("Restart","public restart","en","web",0),"restart");
        var cycle=tracking.check(topic.id(),"first");
        context.close(); context=open();
        assertEquals(cycle.id(),context.getBean(com.infoexplorer.javaapi.tracking.TrackingRepository.class).check(topic.id(),"first").id());
    }

    @Test void upgradesLanguageWithoutRewritingReports() {
        var jdbc=context.getBean(JdbcTemplate.class);
        String en=LanguageMigrationChecks.seed(jdbc,"en"),zh=LanguageMigrationChecks.seed(jdbc,"zh");
        context.close();context=open();
        LanguageMigrationChecks.verify(context.getBean(ResearchRepository.class),context.getBean(JdbcTemplate.class),en,zh);
    }

    @Test void webSnapshotSurvivesRetryAndRestart() {
        var store=context.getBean(ResearchRepository.class);
        String task=store.create("public topic","web-key","en","web").id();
        var first=store.claimNext().orElseThrow();
        store.finishWeb(first,WebFixtures.report(first.runId(),first.question(),"en",true));
        store.retry(task,first.runId()); var second=store.claimNext().orElseThrow();
        store.finishWeb(second,WebFixtures.report(second.runId(),second.question(),"en",false));
        context.close(); context=open(); store=context.getBean(ResearchRepository.class);
        assertEquals("web",store.find(task).orElseThrow().researchMode());
        assertEquals(second.runId(),store.find(task).orElseThrow().webResult().outcome().runId());
        assertEquals(1,store.webRun(task,first.runId()).orElseThrow().outcome().evidence().size());
        assertEquals("FAILED",store.webRun(task,first.runId()).orElseThrow().outcome().status());
        assertNull(store.find(task).orElseThrow().result());
        assertEquals(2,store.history(task).size());
    }

    @Test void upgradesModelSessionFromV6() {
        String old=UUID.randomUUID().toString();
        context.getBean(JdbcTemplate.class).update("INSERT INTO research_task(id,question,status,created_at,updated_at,research_mode) VALUES (?, 'legacy', 'FAILED', 1, 1, 'web')",old);
        context.close(); context=open();
        var store=context.getBean(ResearchRepository.class);
        assertEquals("web",store.find(old).orElseThrow().researchMode());
        assertNull(store.find(old).orElseThrow().modelSession());
        String id=store.create("public topic","model-mysql","en","web-model").id();
        var first=store.claimNext().orElseThrow();
        store.finishSession(first,SessionFixtures.report("fail-report",first.runId(),"en"));
        store.retry(id,first.runId());var second=store.claimNext().orElseThrow();
        store.finishSession(second,SessionFixtures.report("supplement",second.runId(),"en"));
        context.close();context=open();store=context.getBean(ResearchRepository.class);
        assertEquals("SUPPLEMENT_ROUND_LIMIT",store.find(id).orElseThrow().modelSession().session().stopReason());
        assertFalse(store.sessionRun(id,first.runId()).orElseThrow().session().outcome().evidence().isEmpty());
        assertTrue(store.sessionRun(old,first.runId()).isEmpty());
        assertEquals(2,store.history(id).size());
    }

    @Test void upgradesPlanKeepingOldReport() {
        String id=LanguageMigrationChecks.seed(context.getBean(JdbcTemplate.class),"en");
        context.close();context=open();
        var report=context.getBean(ResearchRepository.class).find(id).orElseThrow().result();
        assertEquals("unchanged",report.answer());assertNull(report.plan());
    }

    @Test
    void listingFiltersAndPaginatesWithStableTies() {
        var jdbc = context.getBean(JdbcTemplate.class);
        var store = context.getBean(ResearchRepository.class);
        var a = store.create("first", null);
        var b = store.create("second", null);
        store.create("different status", null);
        jdbc.update("UPDATE research_task SET created_at=1, status='FAILED' WHERE id IN (?, ?)", a.id(), b.id());
        var first = store.list(0, 1, ResearchTask.Status.FAILED);
        var second = store.list(1, 1, ResearchTask.Status.FAILED);
        assertTrue(first.hasNext()); assertFalse(second.hasNext());
        assertTrue(first.items().getFirst().id().compareTo(second.items().getFirst().id()) > 0);
        assertEquals(3, store.list(0, 100, null).items().size());
        assertTrue(store.list(2, 1, ResearchTask.Status.FAILED).items().isEmpty());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='research_task' AND index_name='idx_research_task_created' AND seq_in_index=1", Integer.class));
    }

    @Test void concurrentRetriesKeepHistoryAndEnforceLimit() throws Exception {
        var store = context.getBean(ResearchRepository.class);
        RetryChecks.concurrencyAndHistory(store);
        RetryChecks.cap(store);
        var before = store.list(0, 20, null);
        var histories = before.items().stream().map(t -> store.history(t.id())).toList();
        context.close(); context = open();
        var reopened = context.getBean(ResearchRepository.class);
        assertEquals(before, reopened.list(0, 20, null));
        assertEquals(histories, before.items().stream().map(t -> reopened.history(t.id())).toList());
    }

    @Test void upgradesExistingRunsForRetry() {
        var jdbc = context.getBean(JdbcTemplate.class);
        String taskId = UUID.randomUUID().toString(), runId = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO research_task(id,question,status,created_at,updated_at) VALUES (?, 'legacy failed', 'FAILED', 1, 2)", taskId);
        jdbc.update("INSERT INTO research_run(id,task_id,status,started_at,completed_at,error_code) VALUES (?,?,'FAILED',1,2,'MODEL_TIMEOUT')", runId, taskId);
        context.close(); context = open();
        var store = context.getBean(ResearchRepository.class);
        assertEquals(runId, store.find(taskId).orElseThrow().runId());
        store.retry(taskId, runId);
        var next = store.claimNext().orElseThrow();
        store.fail(next, "SEARCH_TIMEOUT");
        assertEquals(2, store.history(taskId).size());
        assertEquals("MODEL_TIMEOUT", store.history(taskId).getFirst().errorCode());
        assertEquals(1, context.getBean(JdbcTemplate.class).queryForObject("SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='research_run' AND constraint_name='fk_run_task'", Integer.class));
    }

    @Test
    void reportAndEvidenceRollbackTogetherAndSurviveApplicationRestart() {
        var store = context.getBean(ResearchRepository.class);
        var task = store.create("MySQL 持久化 😀", "persist", "zh");
        var claim = store.claimNext().orElseThrow();
        assertEquals("zh", claim.language());
        var base = ReportFixtures.report("研究报告 [E1] 😀", List.of("https://example.org/evidence"));
        var report = ReportFixtures.planned(new ResearchReport(base.answer(), base.sources(), base.provider(), base.query(), base.retrievedAt(),
                base.evidence(), new Generation("fixture", "models.example.org", "evidence-report-v1", "a".repeat(64))));
        var evidence = report.evidence().getFirst();
        var duplicate = new ResearchReport(report.answer(), report.sources(), report.provider(), report.query(), report.retrievedAt(), List.of(evidence, evidence));
        assertThrows(DataAccessException.class, () -> store.succeed(claim, duplicate));
        assertEquals(ResearchTask.Status.RUNNING, store.find(task.id()).orElseThrow().status());
        assertNull(store.find(task.id()).orElseThrow().result());
        assertEquals(0, context.getBean(JdbcTemplate.class).queryForObject("SELECT COUNT(*) FROM research_evidence", Integer.class));
        store.succeed(claim, report);
        var expected = store.find(task.id()).orElseThrow();
        context.close();
        context = open();
        assertEquals(expected, context.getBean(ResearchRepository.class).find(task.id()).orElseThrow());
    }

    @Test
    void concurrentIdempotencyClaimAndRecovery() throws Exception {
        var service = context.getBean(ResearchService.class);
        var store = context.getBean(ResearchRepository.class);
        try (var pool = Executors.newFixedThreadPool(8)) {
            var creations = pool.invokeAll(IntStream.range(0, 8).mapToObj(i ->
                    (Callable<ResearchTask>) () -> service.create("same question", "same-key")).toList());
            String id = creations.getFirst().get().id();
            for (var future : creations) assertEquals(id, future.get().id());
            assertThrows(ResearchException.class, () -> service.create("different", "same-key"));
            var claims = pool.invokeAll(IntStream.range(0, 8).mapToObj(i ->
                    (Callable<java.util.Optional<ResearchRepository.Claim>>) store::claimNext).toList());
            int winners = 0;
            ResearchRepository.Claim winner = null;
            for (var future : claims) {
                var result = future.get();
                if (result.isPresent()) { winners++; winner = result.get(); }
            }
            assertEquals(1, winners);
            assertEquals(1, store.recoverInterrupted());
            var stale = winner;
            assertThrows(IllegalStateException.class, () -> store.succeed(stale, ReportFixtures.report("late", List.of())));
            assertEquals("EXECUTION_INTERRUPTED", store.find(id).orElseThrow().errorCode());
            assertEquals(1, context.getBean(JdbcTemplate.class).queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
        }
    }
}
