package com.infoexplorer.javaapi;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import tools.jackson.databind.json.JsonMapper;
import com.infoexplorer.javaapi.research.TaskPage;

import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import static org.junit.jupiter.api.Assertions.*;

@ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"spring.datasource.url=jdbc:h2:mem:task-list;DB_CLOSE_DELAY=-1", "research.worker.enabled=false"})
class TaskListApiTests {
    @Value("${local.server.port}") int port;
    @Autowired JdbcTemplate jdbc;
    @Autowired JsonMapper mapper;
    final HttpClient http = HttpClient.newHttpClient();

    @BeforeEach void reset() {
        jdbc.update("DELETE FROM research_evidence");
        jdbc.update("DELETE FROM research_execution_control");
        jdbc.update("DELETE FROM research_run");
        jdbc.update("DELETE FROM research_task");
    }

    HttpResponse<String> get(String query) throws Exception {
        return http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/research-tasks" + query))
                .timeout(Duration.ofSeconds(5)).GET().build(), HttpResponse.BodyHandlers.ofString());
    }

    TaskPage page(String query) throws Exception {
        var response = get(query);
        assertEquals(200, response.statusCode());
        return mapper.readValue(response.body(), TaskPage.class);
    }

    void insert(int id, String status, long time) {
        jdbc.update("INSERT INTO research_task(id, question, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                String.format("00000000-0000-0000-0000-%012d", id), "question " + id, status, time, time);
    }

    @Test void emptyAndOutOfRangePages() throws Exception {
        var empty = page("");
        assertEquals(0, empty.page()); assertEquals(20, empty.size());
        assertTrue(empty.items().isEmpty()); assertFalse(empty.hasNext());
        insert(1, "PENDING", 1);
        assertTrue(page("?page=10000&size=100").items().isEmpty());
        assertFalse(page("?page=10000&size=100").hasNext());
    }

    @Test void stableTiesAndNextPageWithoutLoadingReports() throws Exception {
        insert(1, "PENDING", 1); insert(2, "PENDING", 1); insert(3, "PENDING", 2);
        var first = page("?size=2");
        assertEquals(java.util.List.of("question 3", "question 2"), first.items().stream().map(TaskPage.Item::question).toList());
        assertTrue(first.hasNext());
        var last = page("?size=2&page=1");
        assertEquals("question 1", last.items().getFirst().question()); assertFalse(last.hasNext());
        assertEquals(first, page("?size=2"));
        var json = mapper.readTree(get("?size=2").body()).get("items").get(0);
        assertEquals(5, json.size()); assertFalse(json.has("result")); assertFalse(json.has("idempotencyKey"));
        assertEquals(3, jdbc.queryForObject("SELECT COUNT(*) FROM research_task", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM research_run", Integer.class));
    }

    @ParameterizedTest @ValueSource(strings = {"PENDING", "RUNNING", "SUCCEEDED", "FAILED"})
    void filtersBeforePaginating(String status) throws Exception {
        int id = 1;
        for (var state : com.infoexplorer.javaapi.research.ResearchTask.Status.values()) {
            insert(id++, state.name(), 1); insert(id++, state.name(), 1);
        }
        var first = page("?size=1&status=" + status);
        var second = page("?size=1&page=1&status=" + status);
        assertTrue(first.hasNext()); assertFalse(second.hasNext());
        assertEquals(status, first.items().getFirst().status().name());
        assertEquals(status, second.items().getFirst().status().name());
        assertNotEquals(first.items().getFirst().id(), second.items().getFirst().id());
    }

    @ParameterizedTest @ValueSource(strings = {"page=-1", "page=10001", "page=99999999999999999", "page=1.5",
            "page=", "size=0", "size=101", "size=abc", "size=", "status=done", "status=failed", "status=",
            "page=0&page=1", "status=FAILED&status=PENDING", "sort=id", "status=FAILED%27OR%271%27=%271"})
    void invalidQueriesReturnSafe400(String query) throws Exception {
        var response = get("?" + query);
        assertEquals(400, response.statusCode());
        assertEquals("INVALID_QUERY", mapper.readTree(response.body()).get("code").asText());
    }
}
