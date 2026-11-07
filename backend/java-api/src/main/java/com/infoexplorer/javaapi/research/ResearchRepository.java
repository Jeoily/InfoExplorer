package com.infoexplorer.javaapi.research;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class ResearchRepository {
    private static final String SELECT = """
            SELECT t.id, t.question, t.status, t.created_at, t.updated_at, t.search_language,
                   r.id AS run_id, r.started_at, r.completed_at, r.answer, r.sources_json, r.error_code,
                   r.report_provider, r.search_query, r.retrieved_at, r.generation_json, r.plan_json,
                   t.research_mode, r.web_result_json, r.model_session_json
            FROM research_task t LEFT JOIN research_run r ON r.task_id = t.id AND r.attempt_no = t.attempt_no
            """;
    private final JdbcTemplate jdbc;
    private final JsonMapper mapper;

    public ResearchRepository(JdbcTemplate jdbc, JsonMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    public Optional<ResearchTask> find(String id) {
        return jdbc.query(SELECT + " WHERE t.id = ?", this::map, id).stream().findFirst();
    }

    public TaskPage list(int page, int size, ResearchTask.Status status) {
        String sql = "SELECT id, question, status, created_at, updated_at FROM research_task"
                + (status == null ? "" : " WHERE status = ?")
                + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?";
        Object[] parameters = status == null ? new Object[]{size + 1, (long) page * size}
                : new Object[]{status.name(), size + 1, (long) page * size};
        var rows = jdbc.query(sql, (r, i) -> new TaskPage.Item(r.getString("id"), r.getString("question"),
                ResearchTask.Status.valueOf(r.getString("status")), Instant.ofEpochMilli(r.getLong("created_at")),
                Instant.ofEpochMilli(r.getLong("updated_at"))), parameters);
        return new TaskPage(List.copyOf(rows.subList(0, Math.min(size, rows.size()))), page, size, rows.size() > size);
    }

    public Optional<ResearchTask> findByKey(String key) {
        return jdbc.query(SELECT + " WHERE t.idempotency_key = ?", this::map, key).stream().findFirst();
    }

    @Transactional
    public ResearchTask create(String question, String key) {
        return create(question, key, "en");
    }

    @Transactional
    public ResearchTask create(String question, String key, String language) {
        return create(question, key, language, "wikipedia");
    }

    @Transactional
    public ResearchTask create(String question, String key, String language, String mode) {
        String id = UUID.randomUUID().toString();
        long now = System.currentTimeMillis();
        jdbc.update("INSERT INTO research_task(id, question, idempotency_key, status, created_at, updated_at, search_language, research_mode) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?)",
                id, question, key, now, now, language, mode);
        return find(id).orElseThrow();
    }

    public record Claim(String taskId, String runId, String question, String language, String researchMode) {}

    public List<RunSummary> history(String taskId) {
        return jdbc.query("SELECT id, attempt_no, status, started_at, completed_at, error_code, retry_accepted FROM research_run WHERE task_id=? ORDER BY attempt_no",
                (r, i) -> new RunSummary(r.getString("id"), r.getInt("attempt_no"), ResearchTask.Status.valueOf(r.getString("status")),
                        nullableTime(r, "started_at"), nullableTime(r, "completed_at"), r.getString("error_code"), r.getBoolean("retry_accepted")), taskId);
    }

    @Transactional
    public ResearchTask retry(String taskId, String failedRunId) {
        var locked = jdbc.queryForList("SELECT id FROM research_task WHERE id=? FOR UPDATE", String.class, taskId);
        if (locked.isEmpty()) { throw new ResearchException(ResearchException.Reason.NOT_FOUND); }
        var runs = jdbc.queryForList("SELECT retry_accepted FROM research_run WHERE task_id=? AND id=? AND status='FAILED'",
                Boolean.class, taskId, failedRunId);
        if (runs.isEmpty()) { throw new ResearchException(ResearchException.Reason.RETRY_CONFLICT); }
        // A late duplicate refers to the same failed attempt, never to a later failure.
        if (runs.getFirst()) { return find(taskId).orElseThrow(); }
        var current = find(taskId).orElseThrow();
        if (current.status() != ResearchTask.Status.FAILED || !failedRunId.equals(current.runId())) {
            throw new ResearchException(ResearchException.Reason.RETRY_CONFLICT);
        }
        int attempt = jdbc.queryForObject("SELECT attempt_no FROM research_task WHERE id=?", Integer.class, taskId);
        if (attempt >= 5) { throw new ResearchException(ResearchException.Reason.RETRY_LIMIT); }
        jdbc.update("UPDATE research_run SET retry_accepted=TRUE WHERE id=? AND task_id=?", failedRunId, taskId);
        jdbc.update("UPDATE research_task SET status='PENDING', attempt_no=attempt_no+1, updated_at=? WHERE id=?",
                System.currentTimeMillis(), taskId);
        return find(taskId).orElseThrow();
    }

    @Transactional
    public Optional<Claim> claimNext() {
        List<String> ids = jdbc.queryForList("SELECT id FROM research_task WHERE status = 'PENDING' ORDER BY created_at, id LIMIT 1", String.class);
        if (ids.isEmpty()) { return Optional.empty(); }
        String id = ids.getFirst();
        long now = System.currentTimeMillis();
        // Conditional update is the claim: only one contender may create a run.
        if (jdbc.update("UPDATE research_task SET status = 'RUNNING', updated_at = ? WHERE id = ? AND status = 'PENDING'", now, id) != 1) {
            return Optional.empty();
        }
        String runId = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO research_run(id, task_id, status, started_at, attempt_no) SELECT ?, id, 'RUNNING', ?, attempt_no FROM research_task WHERE id=?", runId, now, id);
        jdbc.update("INSERT INTO research_execution_control(run_id,stage,updated_at) VALUES(?,'starting',?)",runId,now);
        var task = find(id).orElseThrow();
        return Optional.of(new Claim(id, runId, task.question(), task.language(), task.researchMode()));
    }

    @Transactional
    public void succeed(Claim claim, ResearchReport response) {
        lockTask(claim);
        if (cancelled(claim.runId())) { fail(claim,"EXECUTION_CANCELLED"); return; }
        long now = System.currentTimeMillis();
        int updated = jdbc.update("UPDATE research_run SET status = 'SUCCEEDED', completed_at = ?, answer = ?, sources_json = ?, report_provider = ?, search_query = ?, retrieved_at = ?, generation_json = ?, plan_json = ? WHERE id = ? AND task_id = ? AND status = 'RUNNING'",
                now, response.answer(), mapper.writeValueAsString(response.sources()), response.provider(), response.query(),
                response.retrievedAt().toEpochMilli(), response.generation() == null ? null : mapper.writeValueAsString(response.generation()), response.plan() == null ? null : mapper.writeValueAsString(response.plan()), claim.runId(), claim.taskId());
        finishTask(claim, updated, "SUCCEEDED", now);
        int position = 0;
        for (Evidence item : response.evidence()) {
            jdbc.update("INSERT INTO research_evidence(run_id, evidence_id, position, url, title, excerpt, retrieved_at, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    claim.runId(), item.id(), position++, item.url(), item.title(), item.excerpt(), item.retrievedAt().toEpochMilli(), item.contentHash());
        }
    }

    @Transactional
    public void fail(Claim claim, String code) {
        lockTask(claim);
        if (cancelled(claim.runId())) code="EXECUTION_CANCELLED";
        long now = System.currentTimeMillis();
        int updated = jdbc.update("UPDATE research_run SET status = 'FAILED', completed_at = ?, error_code = ? WHERE id = ? AND task_id = ? AND status = 'RUNNING'",
                now, code, claim.runId(), claim.taskId());
        finishTask(claim, updated, "FAILED", now);
    }

    @Transactional
    public void finishWeb(Claim claim, WebReport response) {
        lockTask(claim);
        if (cancelled(claim.runId())) { fail(claim,"EXECUTION_CANCELLED"); return; }
        if (!claim.runId().equals(response.outcome().runId())) { throw new IllegalArgumentException("Run mismatch"); }
        long now = System.currentTimeMillis();
        String status = response.outcome().status();
        String error = "FAILED".equals(status) ? response.outcome().completionReason() : null;
        boolean success="SUCCEEDED".equals(status);
        String urls=success?mapper.writeValueAsString(response.outcome().sources().stream()
            .filter(s->"READ".equals(s.status())).map(s->s.metadata().resolvedUrl()).distinct().toList()):null;
        int updated = jdbc.update("UPDATE research_run SET status=?, completed_at=?, error_code=?, web_result_json=?, answer=?, sources_json=? WHERE id=? AND task_id=? AND status='RUNNING'",
                status, now, error, mapper.writeValueAsString(response), success?response.outcome().answer():null, urls, claim.runId(), claim.taskId());
        finishTask(claim, updated, status, now);
    }

    public Optional<WebReport> webRun(String taskId, String runId) {
        return jdbc.query("SELECT web_result_json FROM research_run WHERE task_id=? AND id=? AND web_result_json IS NOT NULL",
                (r,i) -> mapper.readValue(r.getString(1), WebReport.class), taskId, runId).stream().findFirst();
    }

    @Transactional
    public void finishSession(Claim claim, ModelSessionReport response) {
        lockTask(claim);
        if (cancelled(claim.runId())) { fail(claim,"EXECUTION_CANCELLED"); return; }
        var session=response.session();
        if (!"web-model".equals(claim.researchMode()) || !claim.runId().equals(session.runId()))
            throw new IllegalArgumentException("Run mismatch");
        var outcome=session.outcome();
        boolean success=outcome!=null && "SUCCEEDED".equals(outcome.status());
        String status=success?"SUCCEEDED":"FAILED";
        String error=success?null:session.stopReason();
        String urls=success?mapper.writeValueAsString(outcome.sources().stream()
            .filter(s->"READ".equals(s.status())).map(s->s.metadata().resolvedUrl()).distinct().toList()):null;
        long now=System.currentTimeMillis();
        int updated=jdbc.update("UPDATE research_run SET status=?, completed_at=?, error_code=?, model_session_json=?, answer=?, sources_json=? WHERE id=? AND task_id=? AND status='RUNNING'",
            status,now,error,mapper.writeValueAsString(response),success?outcome.answer():null,urls,claim.runId(),claim.taskId());
        finishTask(claim,updated,status,now);
    }

    public Optional<ModelSessionReport> sessionRun(String taskId,String runId) {
        return jdbc.query("SELECT model_session_json FROM research_run WHERE task_id=? AND id=? AND model_session_json IS NOT NULL",
            (r,i)->mapper.readValue(r.getString(1),ModelSessionReport.class),taskId,runId).stream().findFirst();
    }

    private void finishTask(Claim claim, int runUpdated, String status, long now) {
        if (runUpdated != 1 || jdbc.update("UPDATE research_task SET status = ?, updated_at = ? WHERE id = ? AND status = 'RUNNING'",
                status, now, claim.taskId()) != 1) {
            throw new IllegalStateException("Execution is no longer owned by this worker");
        }
    }

    @Transactional
    public int recoverInterrupted() {
        // Safe only for the documented single-instance embedded database deployment.
        long now = System.currentTimeMillis();
        jdbc.update("UPDATE research_run SET status = 'FAILED', completed_at = ?, error_code = CASE WHEN id IN (SELECT run_id FROM research_execution_control WHERE cancel_requested=TRUE) THEN 'EXECUTION_CANCELLED' ELSE 'EXECUTION_INTERRUPTED' END WHERE status = 'RUNNING'", now);
        return jdbc.update("UPDATE research_task SET status = 'FAILED', updated_at = ? WHERE status = 'RUNNING'", now);
    }

    public record Progress(String runId,String stage,boolean cancelRequested,int reused,Instant updatedAt) {}
    private void lockTask(Claim claim) {
        jdbc.queryForList("SELECT id FROM research_task WHERE id=? FOR UPDATE",String.class,claim.taskId());
    }

    public Progress progress(String taskId) {
        var task=find(taskId).orElseThrow(()->new ResearchException(ResearchException.Reason.NOT_FOUND));
        var rows=jdbc.query("SELECT * FROM research_execution_control WHERE run_id=?",(r,i)->new Progress(
            r.getString("run_id"),r.getString("stage"),r.getBoolean("cancel_requested"),r.getInt("reused"),
            Instant.ofEpochMilli(r.getLong("updated_at"))),task.runId());
        var p=rows.isEmpty()?new Progress(task.runId(),"starting",false,0,task.updatedAt()):rows.getFirst();
        return task.status()==ResearchTask.Status.RUNNING?p:new Progress(task.runId(),
            task.status()==ResearchTask.Status.PENDING?"queued":"finished",p.cancelRequested(),p.reused(),task.updatedAt());
    }

    public boolean cancelled(String runId) {
        return !jdbc.queryForList("SELECT run_id FROM research_execution_control WHERE run_id=? AND cancel_requested=TRUE",String.class,runId).isEmpty();
    }

    public void recordProgress(String runId,String stage,int reused) {
        if (!java.util.Set.of("starting","plan","search","read","review","report","verify","finished").contains(stage) || reused<0 || reused>13) return;
        jdbc.update("UPDATE research_execution_control SET stage=?,reused=?,updated_at=? WHERE run_id=? AND run_id IN (SELECT id FROM research_run WHERE status='RUNNING')",
            stage,reused,System.currentTimeMillis(),runId);
    }

    public String resumeFrom(Claim claim) {
        return jdbc.queryForList("SELECT id FROM research_run WHERE task_id=? AND id<>? AND status='FAILED' ORDER BY attempt_no DESC LIMIT 1",String.class,
            claim.taskId(),claim.runId()).stream().findFirst().orElse(null);
    }
    public List<String> interruptedRunIds() {
        return jdbc.queryForList("SELECT id FROM research_run WHERE status='RUNNING'",String.class);
    }

    @Transactional
    public ResearchTask cancel(String taskId,String expectedRunId) {
        if(jdbc.queryForList("SELECT id FROM research_task WHERE id=? FOR UPDATE",String.class,taskId).isEmpty())
            throw new ResearchException(ResearchException.Reason.NOT_FOUND);
        var task=find(taskId).orElseThrow();
        if(task.status()==ResearchTask.Status.FAILED && "EXECUTION_CANCELLED".equals(task.errorCode())
            && (expectedRunId==null || expectedRunId.equals(task.runId()))) return task;
        if(!java.util.Objects.equals(task.runId(),expectedRunId)) throw new ResearchException(ResearchException.Reason.RETRY_CONFLICT);
        if(task.status()==ResearchTask.Status.PENDING) {
            long now=System.currentTimeMillis();
            String run=UUID.randomUUID().toString();
            jdbc.update("INSERT INTO research_run(id,task_id,status,started_at,completed_at,error_code,attempt_no) SELECT ?,id,'FAILED',?,?,'EXECUTION_CANCELLED',attempt_no FROM research_task WHERE id=?",run,now,now,taskId);
            jdbc.update("UPDATE research_task SET status='FAILED',updated_at=? WHERE id=?",now,taskId);
        } else if(task.status()==ResearchTask.Status.RUNNING) {
            jdbc.update("UPDATE research_execution_control SET cancel_requested=TRUE,updated_at=? WHERE run_id=?",System.currentTimeMillis(),expectedRunId);
        }
        return find(taskId).orElseThrow();
    }

    private ResearchTask map(ResultSet row, int index) throws SQLException {
        String runId = row.getString("run_id");
        ResearchReport result = null;
        if (row.getString("answer") != null && "wikipedia".equals(row.getString("research_mode"))) {
            var evidence = jdbc.query("SELECT * FROM research_evidence WHERE run_id = ? ORDER BY position",
                    (r, i) -> new Evidence(r.getString("evidence_id"), r.getString("url"), r.getString("title"),
                            r.getString("excerpt"), Instant.ofEpochMilli(r.getLong("retrieved_at")), r.getString("content_hash")), runId);
            boolean legacy = row.getString("report_provider") == null;
            result = new ResearchReport(row.getString("answer"), mapper.readValue(row.getString("sources_json"), new TypeReference<List<String>>() {}),
                    legacy ? "legacy-mock" : row.getString("report_provider"),
                    legacy ? row.getString("question") : row.getString("search_query"),
                    legacy ? null : nullableTime(row, "retrieved_at"), evidence,
                    row.getString("generation_json") == null ? null : mapper.readValue(row.getString("generation_json"), Generation.class),
                    row.getString("plan_json") == null ? null : mapper.readValue(row.getString("plan_json"), SearchPlan.class));
        }
        return new ResearchTask(row.getString("id"), row.getString("question"),
                ResearchTask.Status.valueOf(row.getString("status")),
                Instant.ofEpochMilli(row.getLong("created_at")), Instant.ofEpochMilli(row.getLong("updated_at")),
                row.getString("run_id"), nullableTime(row, "started_at"), nullableTime(row, "completed_at"),
                result, row.getString("error_code"), row.getString("search_language"), row.getString("research_mode"),
                row.getString("web_result_json") == null ? null : mapper.readValue(row.getString("web_result_json"), WebReport.class),
                row.getString("model_session_json") == null ? null : mapper.readValue(row.getString("model_session_json"), ModelSessionReport.class));
    }

    private Instant nullableTime(ResultSet row, String name) throws SQLException {
        long value = row.getLong(name);
        return row.wasNull() ? null : Instant.ofEpochMilli(value);
    }
}
