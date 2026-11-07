package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.ResearchTask;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.server.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import tools.jackson.databind.json.JsonMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

/** Explicit opt-in: one public research task, actual worker, temporary file DB, restart. */
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_MODE", matches = "live-model")
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_URL", matches = "http://127\\.0\\.0\\.1:[0-9]+")
class LiveModelIntegrationTests {
    @TempDir Path directory;
    final HttpClient http = HttpClient.newHttpClient();

    ConfigurableApplicationContext open(boolean worker) {
        return new SpringApplicationBuilder(JavaApiApplication.class).run(
                "--spring.profiles.active=test", "--server.address=127.0.0.1", "--server.port=0",
                "--spring.datasource.url=jdbc:h2:file:" + directory.resolve("live-model").toString().replace('\\', '/') + ";DB_CLOSE_ON_EXIT=FALSE",
                "--agent.service.base-url=" + System.getenv("INFOEXPLORER_TEST_AGENT_URL"),
                "--research.worker.enabled=" + worker, "--research.worker.poll-delay-ms=100",
                "--spring.main.banner-mode=off");
    }

    String base(ConfigurableApplicationContext context) {
        return "http://127.0.0.1:" + ((WebServerApplicationContext) context).getWebServer().getPort()
                + "/api/v1/research-tasks";
    }

    HttpResponse<String> submit(String base) throws Exception {
        return http.send(HttpRequest.newBuilder(URI.create(base)).timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json").header("Idempotency-Key", "live-model-single-task")
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"artificial intelligence\"}")).build(),
                HttpResponse.BodyHandlers.ofString());
    }

    ResearchTask fetch(String url, JsonMapper mapper) throws Exception {
        var response = http.send(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(5)).GET().build(),
                HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        return mapper.readValue(response.body(), ResearchTask.class);
    }

    @Test
    void realModelReportSurvivesWorkerExecutionIdempotentReplayAndRestart() throws Exception {
        ResearchTask completed;
        try (var first = open(true)) {
            var mapper = first.getBean(JsonMapper.class);
            String base = base(first);
            var accepted = submit(base);
            assertEquals(202, accepted.statusCode());
            var created = mapper.readValue(accepted.body(), ResearchTask.class);
            assertTrue(accepted.headers().firstValue("Location").orElseThrow().endsWith(created.id()));
            long deadline = System.nanoTime() + Duration.ofSeconds(75).toNanos();
            do {
                completed = fetch(base + "/" + created.id(), mapper);
                if (completed.status() == ResearchTask.Status.SUCCEEDED || completed.status() == ResearchTask.Status.FAILED) break;
                Thread.sleep(200);
            } while (System.nanoTime() < deadline);
            assertEquals(ResearchTask.Status.SUCCEEDED, completed.status(), completed.errorCode());
            assertNotNull(completed.result().generation(), "Model must actually be enabled in Python");
            assertEquals("agnes-2.5-flash", completed.result().generation().model());
            assertEquals("api.agnes-ai.cn", completed.result().generation().host());
            assertEquals("evidence-report-v2", completed.result().generation().promptVersion());
            assertEquals("wikipedia-en", completed.result().provider());
            assertFalse(completed.result().evidence().isEmpty());
            assertFalse(completed.result().answer().isBlank());
            var replay = submit(base);
            assertEquals(202, replay.statusCode());
            assertEquals(completed, mapper.readValue(replay.body(), ResearchTask.class));
            var jdbc = first.getBean(JdbcTemplate.class);
            assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM research_task", Integer.class));
            assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
            assertEquals(completed.result().evidence().size(), jdbc.queryForObject("SELECT COUNT(*) FROM research_evidence", Integer.class));
            System.out.printf("LIVE_MODEL_CHECK status=%s evidence=%d model=%s inputHash=%s%n",
                    completed.status(), completed.result().evidence().size(), completed.result().generation().model(),
                    completed.result().generation().inputHash());
        }
        // The worker is disabled on restart, so only persisted data can satisfy these checks.
        try (var reopened = open(false)) {
            assertEquals(completed, fetch(base(reopened) + "/" + completed.id(), reopened.getBean(JsonMapper.class)));
            assertEquals(1, reopened.getBean(JdbcTemplate.class).queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
            System.out.println("LIVE_MODEL_CHECK restart=passed idempotentReplay=passed runs=1");
        }
    }
}
