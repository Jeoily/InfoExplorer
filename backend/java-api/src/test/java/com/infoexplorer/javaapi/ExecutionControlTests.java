package com.infoexplorer.javaapi;
import com.infoexplorer.javaapi.research.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ExecutionControlTests extends WebResearchTests {
    @Test void cancellationRacesCompletionWithoutOverwritingEitherWinner() throws Exception {
        try(var app=open();var pool=java.util.concurrent.Executors.newFixedThreadPool(2)) {
            var repo=app.getBean(ResearchRepository.class);
            var task=repo.create("public topic",null,"en","web-model");
            var claim=repo.claimNext().orElseThrow();
            var start=new java.util.concurrent.CountDownLatch(1);
            var cancel=pool.submit(()->{start.await();return repo.cancel(task.id(),claim.runId());});
            var complete=pool.submit(()->{start.await();repo.finishSession(claim,SessionFixtures.report("public-topic",claim.runId(),"en"));return true;});
            start.countDown();cancel.get(5,java.util.concurrent.TimeUnit.SECONDS);complete.get(5,java.util.concurrent.TimeUnit.SECONDS);
            var finalTask=repo.find(task.id()).orElseThrow();
            if(finalTask.status()==ResearchTask.Status.FAILED) {
                assertEquals("EXECUTION_CANCELLED",finalTask.errorCode()); assertNull(finalTask.modelSession());
            } else { assertEquals(ResearchTask.Status.SUCCEEDED,finalTask.status()); assertNotNull(finalTask.modelSession()); }
            assertEquals(1,repo.history(task.id()).size());
        }
    }
    @Test void cancellationRecoveryAndRetryFencing() {
        try(var app=open()) { ExecutionChecks.lifecycle(app.getBean(ResearchRepository.class)); }
    }
    @Test void cancellationAndProgressSurviveRestart() {
        String id,run;
        try(var app=open()) {
            var repo=app.getBean(ResearchRepository.class);
            id=repo.create("restart pending cancellation",null).id();
            run=repo.claimNext().orElseThrow().runId();
            repo.recordProgress(run,"report",1); repo.cancel(id,run);
        }
        try(var app=open()) {
            var repo=app.getBean(ResearchRepository.class);
            assertTrue(repo.progress(id).cancelRequested());
            assertEquals("report",repo.progress(id).stage());
            repo.recoverInterrupted();
            assertEquals("EXECUTION_CANCELLED",repo.find(id).orElseThrow().errorCode());
        }
    }
}
