package com.infoexplorer.javaapi.controller;

import com.infoexplorer.javaapi.dto.ResearchRequest;
import com.infoexplorer.javaapi.research.ResearchService;
import com.infoexplorer.javaapi.research.ResearchTask;
import com.infoexplorer.javaapi.research.TaskPage;
import org.springframework.util.MultiValueMap;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequestMapping("/api/v1/research-tasks")
public class ResearchController {
    private final ResearchService service;

    public ResearchController(ResearchService service) { this.service = service; }

    @PostMapping
    public ResponseEntity<ResearchTask> create(@Valid @RequestBody ResearchRequest request,
            @RequestHeader(value = "Idempotency-Key", required = false) String key) {
        ResearchTask task = service.create(request.question(), key, request.language(), request.researchMode());
        return ResponseEntity.accepted().location(URI.create("/api/v1/research-tasks/" + task.id())).body(task);
    }

    @GetMapping("/{id}")
    public ResearchTask get(@PathVariable String id) { return service.get(id); }

    public record RetryRequest(String failedRunId) {}
    public record CancelRequest(String expectedRunId) {}

    @PostMapping("/{id}/cancel")
    public ResponseEntity<ResearchTask> cancel(@PathVariable String id,@RequestBody CancelRequest request) {
        return ResponseEntity.accepted().body(service.cancel(id,request.expectedRunId()));
    }

    @GetMapping("/{id}/progress")
    public com.infoexplorer.javaapi.research.ResearchRepository.Progress progress(@PathVariable String id) {
        return service.progress(id);
    }

    @PostMapping("/{id}/retry")
    public ResponseEntity<ResearchTask> retry(@PathVariable String id, @RequestBody RetryRequest request) {
        var task = service.retry(id, request.failedRunId());
        return ResponseEntity.accepted().location(URI.create("/api/v1/research-tasks/" + task.id())).body(task);
    }

    @GetMapping("/{id}/runs")
    public java.util.List<com.infoexplorer.javaapi.research.RunSummary> history(@PathVariable String id) {
        return service.history(id);
    }

    @GetMapping("/{id}/runs/{runId}/web-result")
    public com.infoexplorer.javaapi.research.WebReport webRun(@PathVariable String id, @PathVariable String runId) {
        return service.webRun(id,runId);
    }

    @GetMapping
    public TaskPage list(@RequestParam MultiValueMap<String, String> query) {
        return service.list(query);
    }

    @GetMapping("/{id}/runs/{runId}/model-session")
    public com.infoexplorer.javaapi.research.ModelSessionReport sessionRun(@PathVariable String id,@PathVariable String runId) {
        return service.sessionRun(id,runId);
    }
}
