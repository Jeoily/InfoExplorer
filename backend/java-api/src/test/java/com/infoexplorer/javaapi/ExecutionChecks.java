package com.infoexplorer.javaapi;
import com.infoexplorer.javaapi.research.*;
import static org.junit.jupiter.api.Assertions.*;

final class ExecutionChecks {
    static void lifecycle(ResearchRepository repo) {
        var queued=repo.create("cancel queued",null,"en","web-model");
        var cancelled=repo.cancel(queued.id(),null);
        assertEquals("EXECUTION_CANCELLED",cancelled.errorCode());
        assertTrue(repo.claimNext().isEmpty());
        repo.retry(queued.id(),cancelled.runId());
        var active=repo.claimNext().orElseThrow();
        assertThrows(ResearchException.class,()->repo.cancel(queued.id(),cancelled.runId()));
        repo.recordProgress(active.runId(),"read",2);
        assertEquals("read",repo.progress(queued.id()).stage());
        repo.cancel(queued.id(),active.runId());
        repo.cancel(queued.id(),active.runId());
        assertTrue(repo.progress(queued.id()).cancelRequested());
        repo.finishSession(active,SessionFixtures.report("public-topic",active.runId(),"en"));
        assertEquals("EXECUTION_CANCELLED",repo.find(queued.id()).orElseThrow().errorCode());
        assertNull(repo.find(queued.id()).orElseThrow().modelSession());
        repo.retry(queued.id(),active.runId());
        var resumed=repo.claimNext().orElseThrow();
        assertEquals(active.runId(),repo.resumeFrom(resumed));
        assertFalse(repo.cancelled(resumed.runId()));
        assertThrows(IllegalStateException.class,()->repo.fail(active,"LATE_ERROR"));
        assertEquals(1,repo.recoverInterrupted());
        assertEquals("EXECUTION_INTERRUPTED",repo.find(queued.id()).orElseThrow().errorCode());
        assertEquals("finished",repo.progress(queued.id()).stage());
        assertEquals(3,repo.history(queued.id()).size());
    }
}
