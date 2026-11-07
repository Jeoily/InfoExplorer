package com.infoexplorer.javaapi.research;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;

@Service
public class ResearchService {
    private final ResearchRepository repository;
    private final com.infoexplorer.javaapi.tracking.TrackingRepository tracking;

    public ResearchService(ResearchRepository repository, com.infoexplorer.javaapi.tracking.TrackingRepository tracking) { this.repository = repository; this.tracking=tracking; }

    public TaskPage list(org.springframework.util.MultiValueMap<String, String> query) {
        if (query.entrySet().stream().anyMatch(e -> !java.util.Set.of("page", "size", "status").contains(e.getKey())
                || e.getValue().size() != 1)) {
            throw new ResearchException(ResearchException.Reason.INVALID_QUERY);
        }
        int page = number(query.getFirst("page"), 0, 0, 10000);
        int size = number(query.getFirst("size"), 20, 1, 100);
        ResearchTask.Status status = null;
        if (query.containsKey("status")) {
            try { status = ResearchTask.Status.valueOf(query.getFirst("status")); }
            catch (IllegalArgumentException | NullPointerException exception) {
                throw new ResearchException(ResearchException.Reason.INVALID_QUERY);
            }
        }
        return repository.list(page, size, status);
    }

    private int number(String value, int fallback, int min, int max) {
        if (value == null) { return fallback; }
        if (!value.matches("[0-9]{1,5}")) { throw new ResearchException(ResearchException.Reason.INVALID_QUERY); }
        int parsed = Integer.parseInt(value);
        if (parsed < min || parsed > max) { throw new ResearchException(ResearchException.Reason.INVALID_QUERY); }
        return parsed;
    }

    public ResearchTask create(String question, String key) {
        return create(question, key, "en");
    }

    public ResearchTask create(String question, String key, String language) {
        return create(question, key, language, "wikipedia");
    }

    public ResearchTask create(String question, String key, String language, String mode) {
        if (key != null && !key.matches("[A-Za-z0-9._:-]{1,128}")) {
            throw new ResearchException(ResearchException.Reason.INVALID_KEY);
        }
        if (key != null) {
            var existing = repository.findByKey(key);
            if (existing.isPresent()) { return replay(existing.get(), question, language, mode); }
        }
        try {
            return repository.create(question, key, language, mode);
        } catch (DuplicateKeyException exception) {
            // The losing INSERT transaction has already rolled back before this lookup.
            if (key == null) { throw exception; }
            return replay(repository.findByKey(key).orElseThrow(() -> exception), question, language, mode);
        }
    }

    private ResearchTask replay(ResearchTask existing, String question, String language, String mode) {
        if (!existing.question().equals(question) || !existing.language().equals(language) || !existing.researchMode().equals(mode)) {
            throw new ResearchException(ResearchException.Reason.KEY_CONFLICT);
        }
        return existing;
    }

    public ResearchTask get(String id) {
        return repository.find(validId(id))
                .orElseThrow(() -> new ResearchException(ResearchException.Reason.NOT_FOUND));
    }

    public ResearchRepository.Progress progress(String id) { return repository.progress(validId(id)); }
    public ResearchTask cancel(String id,String runId) {
        return repository.cancel(validId(id),runId==null?null:validId(runId));
    }

    public java.util.List<RunSummary> history(String id) {
        return repository.history(get(id).id());
    }

    public WebReport webRun(String id, String runId) {
        return repository.webRun(get(id).id(),validId(runId))
                .orElseThrow(()->new ResearchException(ResearchException.Reason.NOT_FOUND));
    }

    public ModelSessionReport sessionRun(String id,String runId) {
        return repository.sessionRun(get(id).id(),validId(runId))
            .orElseThrow(()->new ResearchException(ResearchException.Reason.NOT_FOUND));
    }

    public ResearchTask retry(String id, String failedRunId) {
        String taskId = validId(id);
        if (failedRunId == null || !failedRunId.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")) {
            throw new ResearchException(ResearchException.Reason.INVALID_RETRY);
        }
        var cycle=tracking.forTask(taskId);
        if(cycle!=null) {
            tracking.reconcile(cycle.id());
            tracking.retry(cycle.topicId(),cycle.id(),failedRunId);
            return repository.find(taskId).orElseThrow();
        }
        return repository.retry(taskId, failedRunId.toLowerCase(java.util.Locale.ROOT));
    }

    private String validId(String id) {
        if (!id.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")) {
            throw new ResearchException(ResearchException.Reason.INVALID_ID);
        }
        return id.toLowerCase(java.util.Locale.ROOT);
    }
}
