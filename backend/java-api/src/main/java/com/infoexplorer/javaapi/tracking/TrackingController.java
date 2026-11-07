package com.infoexplorer.javaapi.tracking;

import static com.infoexplorer.javaapi.tracking.TrackingModels.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.web.bind.annotation.*;
import org.springframework.dao.DuplicateKeyException;

@RestController
@RequestMapping("/api/v1/tracking-topics")
public class TrackingController {
    private final TrackingRepository repository;
    public TrackingController(TrackingRepository repository) { this.repository=repository; }
    @PostMapping
    public Topic create(@Valid @RequestBody Config config,@RequestHeader(value="Idempotency-Key",required=false) String key) {
        try { return repository.create(config,key); }
        catch(DuplicateKeyException race) { return repository.create(config,key); }
    }
    @GetMapping
    public Page<Topic> list(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size) {
        return repository.list(page,size);
    }
    @GetMapping("/{id}") public Topic get(@PathVariable String id) { return repository.get(id); }
    public record Update(@Min(1) int expectedVersion,@NotNull @Valid Config config,
                         @NotNull @Pattern(regexp="ACTIVE|PAUSED|ARCHIVED") String status) {}
    @PutMapping("/{id}")
    public Topic update(@PathVariable String id,@Valid @RequestBody Update update) {
        return repository.update(id,update.expectedVersion(),update.config(),update.status());
    }
    @GetMapping("/{id}/configs/{version}")
    public Config configuration(@PathVariable String id,@PathVariable int version) { return repository.configuration(id,version); }
    @PostMapping("/{id}/cycles")
    public Cycle check(@PathVariable String id,@RequestHeader(value="Idempotency-Key",required=false) String key) {
        return repository.check(id,key);
    }
    @GetMapping("/{id}/cycles")
    public Page<Cycle> cycles(@PathVariable String id,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size) {
        return repository.cycles(id,page,size);
    }
    @GetMapping("/{id}/cycles/{cycleId}")
    public Cycle cycle(@PathVariable String id,@PathVariable String cycleId) { return repository.getCycle(id,cycleId); }
    public record Retry(@NotNull String failedRunId) {}
    @PostMapping("/{id}/cycles/{cycleId}/retry")
    public Cycle retry(@PathVariable String id,@PathVariable String cycleId,@Valid @RequestBody Retry body) {
        return repository.retry(id,cycleId,body.failedRunId());
    }
    @GetMapping("/{id}/changes")
    public Page<Change> changes(@PathVariable String id,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size) {
        return repository.changes(id,page,size);
    }
}
