package com.infoexplorer.javaapi.tracking;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.slf4j.LoggerFactory;

@Component
@ConditionalOnProperty(name="research.worker.enabled",havingValue="true",matchIfMissing=true)
public class TrackingWorker {
    private final TrackingRepository repository;
    private volatile boolean ready;
    public TrackingWorker(TrackingRepository repository) { this.repository=repository; }
    @Bean(name="trackingScheduler")
    public ThreadPoolTaskScheduler trackingScheduler() {
        var scheduler=new ThreadPoolTaskScheduler(); scheduler.setPoolSize(1);
        scheduler.setThreadNamePrefix("tracking-"); scheduler.setWaitForTasksToCompleteOnShutdown(true);
        scheduler.setAwaitTerminationSeconds(10); return scheduler;
    }
    @EventListener(ApplicationReadyEvent.class) public void ready() { ready=true; }
    @Scheduled(fixedDelayString="${tracking.poll-delay-ms:2000}",scheduler="trackingScheduler")
    public void tick() {
        if(!ready) return;
        try {
            for(String cycle:repository.pending()) {
                try { repository.reconcile(cycle); }
                catch(RuntimeException e) { log(e); }
            }
            long now=System.currentTimeMillis();
            for(String topic:repository.due(now)) {
                try { repository.schedule(topic,now); }
                catch(RuntimeException e) { log(e); }
            }
        } catch(RuntimeException e) { log(e); }
    }
    private void log(RuntimeException e) {
        LoggerFactory.getLogger(TrackingWorker.class).warn("Tracking operation deferred: {}",e.getClass().getSimpleName());
    }
}
