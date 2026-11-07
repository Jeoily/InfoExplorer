package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.tracking.*;
import com.infoexplorer.javaapi.tracking.TrackingModels.*;
import com.infoexplorer.javaapi.research.*;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import static org.junit.jupiter.api.Assertions.*;

final class TrackingChecks {
    static void lifecycle(ConfigurableApplicationContext app) throws Exception {
        var repo=app.getBean(TrackingRepository.class); var research=app.getBean(ResearchRepository.class);
        var jdbc=app.getBean(JdbcTemplate.class);
        String key=UUID.randomUUID().toString();
        var cfg=new Config("Python public docs","public topic","en","web",0);
        var topic=repo.create(cfg,key);
        assertEquals(topic.id(),repo.create(cfg,key).id());
        assertThrows(TrackingException.class,()->repo.create(new Config("other","public topic","en","web",0),key));
        Cycle first;
        try(var pool=Executors.newFixedThreadPool(4)) {
            var results=pool.invokeAll(IntStream.range(0,4).<java.util.concurrent.Callable<Cycle>>mapToObj(i->()->repo.check(topic.id(),"first")).toList());
            first=results.getFirst().get();
            for(var result:results) assertEquals(first.id(),result.get().id());
        }
        assertEquals(1,repo.cycles(topic.id(),0,20).items().size());
        assertThrows(TrackingException.class,()->repo.check(topic.id(),"busy"));
        var run=research.claimNext().orElseThrow();
        research.finishWeb(run,WebFixtures.report(run.runId(),run.question(),"en",false));
        repo.reconcile(first.id()); repo.reconcile(first.id());
        assertEquals("COMPLETED",repo.getCycle(topic.id(),first.id()).status());
        assertEquals(1,repo.changes(topic.id(),0,20).items().size());
        assertEquals("FIRST_SEEN",repo.changes(topic.id(),0,20).items().getFirst().kind());

        var renamed=repo.update(topic.id(),topic.version(),new Config("Renamed","public topic","en","web",0),"ACTIVE");
        assertThrows(TrackingException.class,()->repo.update(topic.id(),1,cfg,"PAUSED"));
        var second=repo.check(topic.id(),"second");
        assertEquals(first.id(),second.baselineCycleId());
        var next=research.claimNext().orElseThrow();
        research.finishWeb(next,WebFixtures.report(next.runId(),next.question(),"en",false));
        repo.reconcile(second.id());
        assertTrue(repo.changes(topic.id(),0,20).items().stream().anyMatch(c->c.cycleId().equals(second.id()) && c.kind().equals("UNCHANGED") && c.previousRevisionId()!=null));
        assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM tracked_source WHERE topic_id=?",Integer.class,topic.id()));

        var failed=repo.check(topic.id(),"failed"); var failure=research.claimNext().orElseThrow();
        research.fail(failure,"AGENT_TIMEOUT"); repo.reconcile(failed.id());
        assertEquals("FAILED",repo.getCycle(topic.id(),failed.id()).status());
        assertEquals(2,repo.changes(topic.id(),0,20).items().size());
        repo.retry(topic.id(),failed.id(),failure.runId()); repo.retry(topic.id(),failed.id(),failure.runId());
        var retry=research.claimNext().orElseThrow(); assertTrue(research.claimNext().isEmpty());
        research.finishWeb(retry,WebFixtures.report(retry.runId(),retry.question(),"en",false)); repo.reconcile(failed.id());
        assertEquals(2,research.history(failed.taskId()).size());
        assertEquals(3,repo.cycles(topic.id(),0,20).items().size());
        repo.update(topic.id(),renamed.version(),cfg,"PAUSED");
        assertThrows(TrackingException.class,()->repo.check(topic.id(),"paused"));
        var foreign=repo.create(cfg,UUID.randomUUID().toString());
        assertThrows(TrackingException.class,()->repo.getCycle(foreign.id(),first.id()));
        assertThrows(TrackingException.class,()->repo.create(new Config("bad","topic","en","web-model",60),UUID.randomUUID().toString()));
    }
    static void changes(ConfigurableApplicationContext app) {
        var repo=app.getBean(TrackingRepository.class); var research=app.getBean(ResearchRepository.class);
        var topic=repo.create(new Config("Changes","public changes","en","web",0),UUID.randomUUID().toString());
        String[] bodies={"Version one","Version two","Version two","Version two"};
        String[] extractors={"fixture","fixture","fixture-v2","fixture-v2"};
        String[] urls={"https://example.org/a","https://example.org/a","https://example.org/a","https://example.org/mirror"};
        String[] kinds={"FIRST_SEEN","UPDATED","EXTRACTOR_CHANGED","FIRST_SEEN"};
        for(int i=0;i<4;i++) {
            var cycle=repo.check(topic.id(),"change-"+i); var run=research.claimNext().orElseThrow();
            research.finishWeb(run,WebFixtures.report(run.runId(),run.question(),"en",false,urls[i],bodies[i],extractors[i]));
            repo.reconcile(cycle.id());
            var change=repo.changes(topic.id(),0,20).items().stream().filter(c->c.cycleId().equals(cycle.id())).findFirst().orElseThrow();
            assertEquals(kinds[i],change.kind());
            assertEquals(i==3,change.possibleDuplicate());
            assertEquals(bodies[i],change.evidence().getFirst().excerpt());
        }
    }
    static void scheduler(ConfigurableApplicationContext app) {
        var repo=app.getBean(TrackingRepository.class); var research=app.getBean(ResearchRepository.class);
        var jdbc=app.getBean(JdbcTemplate.class);
        var topic=repo.create(new Config("Scheduled","public scheduler","en","web",60),UUID.randomUUID().toString());
        long due=topic.nextDueAt().toEpochMilli(),now=due+3*3600000L+50;
        repo.schedule(topic.id(),now); repo.schedule(topic.id(),now);
        var cycle=repo.cycles(topic.id(),0,20).items().getFirst();
        assertEquals(3,cycle.missedSlots()); assertEquals("SCHEDULED",cycle.trigger());
        assertEquals(1,repo.cycles(topic.id(),0,20).items().size());
        repo.schedule(topic.id(),now+3600000L);
        assertEquals(1,repo.cycles(topic.id(),0,20).items().size());
        assertTrue(repo.get(topic.id()).nextDueAt().toEpochMilli()>now+3600000L);
        var run=research.claimNext().orElseThrow();
        assertEquals(1,research.recoverInterrupted()); repo.reconcile(cycle.id());
        assertEquals("FAILED",repo.getCycle(topic.id(),cycle.id()).status());
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM tracked_source WHERE topic_id=?",Integer.class,topic.id()));
    }
}
