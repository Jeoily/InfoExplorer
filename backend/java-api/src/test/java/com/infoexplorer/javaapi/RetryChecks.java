package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.*;
import java.util.List;
import java.util.concurrent.*;
import java.util.stream.IntStream;
import static org.junit.jupiter.api.Assertions.*;

final class RetryChecks {
    static void concurrencyAndHistory(ResearchRepository store) throws Exception {
        var task = store.create("retry fixture", null);
        var old = store.claimNext().orElseThrow();
        store.fail(old, "MODEL_TIMEOUT");
        var start = new CountDownLatch(1);
        try (var pool = Executors.newFixedThreadPool(8)) {
            var calls = IntStream.range(0, 8).mapToObj(i -> pool.submit(() -> {
                start.await(); return store.retry(task.id(), old.runId());
            })).toList();
            start.countDown();
            for (var call : calls) {
                var queued = call.get(10, TimeUnit.SECONDS);
                assertEquals(ResearchTask.Status.PENDING, queued.status());
                assertNull(queued.runId()); assertNull(queued.errorCode()); assertNull(queued.result());
            }
        }
        assertEquals(1, store.history(task.id()).size());
        var second = store.claimNext().orElseThrow();
        assertTrue(store.claimNext().isEmpty());
        assertNotEquals(old.runId(), second.runId());
        assertThrows(IllegalStateException.class, () -> store.succeed(old, ReportFixtures.report("late", List.of())));
        assertEquals(second.runId(), store.find(task.id()).orElseThrow().runId());
        store.fail(second, "SEARCH_TIMEOUT");
        // A delayed first request must not retry the second failure.
        assertEquals(ResearchTask.Status.FAILED, store.retry(task.id(), old.runId()).status());
        assertEquals(2, store.history(task.id()).size());
        store.retry(task.id(), second.runId());
        var third = store.claimNext().orElseThrow();
        var valid = ReportFixtures.report("success", List.of("https://example.org/evidence"));
        var item = valid.evidence().getFirst();
        var duplicate = new ResearchReport(valid.answer(), valid.sources(), valid.provider(), valid.query(), valid.retrievedAt(), List.of(item, item));
        assertThrows(org.springframework.dao.DataAccessException.class, () -> store.succeed(third, duplicate));
        assertEquals(ResearchTask.Status.RUNNING, store.find(task.id()).orElseThrow().status());
        store.succeed(third, valid);
        var history = store.history(task.id());
        assertEquals(List.of(1, 2, 3), history.stream().map(RunSummary::attempt).toList());
        assertEquals("MODEL_TIMEOUT", history.get(0).errorCode());
        assertEquals("SEARCH_TIMEOUT", history.get(1).errorCode());
        assertTrue(history.get(0).retryAccepted()); assertTrue(history.get(1).retryAccepted());
        assertEquals(ResearchTask.Status.SUCCEEDED, store.retry(task.id(), old.runId()).status());
        assertThrows(ResearchException.class, () -> store.retry(task.id(), third.runId()));
        assertEquals(3, store.history(task.id()).size());
        assertEquals(1, store.find(task.id()).orElseThrow().result().evidence().size());
    }

    static void cap(ResearchRepository store) {
        var task = store.create("retry cap", null);
        for (int attempt = 1; attempt <= 5; attempt++) {
            var claim = store.claimNext().orElseThrow();
            store.fail(claim, "MODEL_TIMEOUT");
            if (attempt < 5) { store.retry(task.id(), claim.runId()); }
            else {
                var error = assertThrows(ResearchException.class, () -> store.retry(task.id(), claim.runId()));
                assertEquals(ResearchException.Reason.RETRY_LIMIT, error.reason());
            }
        }
        assertEquals(5, store.history(task.id()).size());
        assertFalse(store.history(task.id()).getLast().retryAccepted());
        assertTrue(store.claimNext().isEmpty());
    }
}
