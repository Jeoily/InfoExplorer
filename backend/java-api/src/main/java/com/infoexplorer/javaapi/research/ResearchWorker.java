package com.infoexplorer.javaapi.research;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@EnableScheduling
@ConditionalOnProperty(name = "research.worker.enabled", havingValue = "true", matchIfMissing = true)
public class ResearchWorker {
    private static final Logger log = LoggerFactory.getLogger(ResearchWorker.class);
    private final ResearchRepository repository;
    private final ResearchExecutor executor;
    private volatile boolean ready;
    private volatile boolean recoveryRequired;

    public ResearchWorker(ResearchRepository repository, ResearchExecutor executor) {
        this.repository = repository;
        this.executor = executor;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void recover() {
        executor.cancelInterrupted();
        int recovered = repository.recoverInterrupted();
        if (recovered > 0) { log.warn("Marked {} interrupted research executions as failed", recovered); }
        ready = true;
    }

    @org.springframework.context.annotation.Bean(name="researchScheduler")
    public org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler researchScheduler() {
        var scheduler=new org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler();
        scheduler.setPoolSize(1); scheduler.setThreadNamePrefix("research-");
        scheduler.setWaitForTasksToCompleteOnShutdown(true); scheduler.setAwaitTerminationSeconds(180);
        return scheduler;
    }

    @Scheduled(fixedDelayString = "${research.worker.poll-delay-ms:500}", scheduler="researchScheduler")
    public void poll() {
        if (!ready) { return; }
        try {
            if(recoveryRequired) {
                executor.cancelInterrupted();
                repository.recoverInterrupted();
                recoveryRequired=false;
            }
            executor.runNext();
        } catch (RuntimeException exception) {
            recoveryRequired=true;
            // Do not log SQL parameters, questions or upstream exception bodies.
            log.error("Research persistence/execution failure; inspect database availability. Exception type: {}",
                    exception.getClass().getSimpleName());
        }
    }
}
