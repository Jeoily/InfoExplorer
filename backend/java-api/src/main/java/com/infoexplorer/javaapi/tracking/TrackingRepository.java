package com.infoexplorer.javaapi.tracking;

import static com.infoexplorer.javaapi.tracking.TrackingModels.*;
import com.infoexplorer.javaapi.research.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.core.type.TypeReference;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Repository
public class TrackingRepository {
    private final JdbcTemplate jdbc;
    private final ResearchRepository research;
    private final JsonMapper mapper;
    public TrackingRepository(JdbcTemplate jdbc, ResearchRepository research, JsonMapper mapper) {
        this.jdbc=jdbc; this.research=research; this.mapper=mapper;
    }
    static String id(String value) {
        if(value==null || !value.matches("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"))
            throw new TrackingException("INVALID_TRACKING_ID",400);
        return value.toLowerCase(Locale.ROOT);
    }
    static void key(String key) {
        if(key==null || !key.matches("[A-Za-z0-9._:-]{1,128}")) throw new TrackingException("INVALID_IDEMPOTENCY_KEY",400);
    }
    static void config(Config c) {
        if(c.scheduleMinutes()!=0 && (c.scheduleMinutes()<60 || !"web".equals(c.researchMode())))
            throw new TrackingException("INVALID_TRACKING_SCHEDULE",400);
    }
    static String uuid() { return UUID.randomUUID().toString(); }
    static Instant time(ResultSet r,String name) throws SQLException {
        long value=r.getLong(name); return r.wasNull()?null:Instant.ofEpochMilli(value);
    }
    Topic topic(ResultSet r,int row) throws SQLException {
        return new Topic(r.getString("id"),r.getString("name"),r.getString("question"),r.getString("language"),
            r.getString("research_mode"),r.getString("status"),r.getInt("version"),r.getInt("schedule_minutes"),
            time(r,"next_due_at"),time(r,"created_at"),time(r,"updated_at"));
    }
    Cycle cycle(ResultSet r,int row) throws SQLException {
        return new Cycle(r.getString("id"),r.getString("topic_id"),r.getInt("config_version"),
            r.getString("trigger_kind"),r.getString("task_id"),r.getString("run_id"),r.getString("baseline_cycle_id"),
            r.getString("status"),r.getString("error_code"),time(r,"created_at"),time(r,"completed_at"),r.getInt("missed_slots"));
    }
    public Topic get(String topicId) {
        return jdbc.query("SELECT * FROM tracking_topic WHERE id=?",this::topic,id(topicId)).stream()
            .findFirst().orElseThrow(()->new TrackingException("TOPIC_NOT_FOUND",404));
    }
    void lock(String topicId) {
        if(jdbc.queryForList("SELECT id FROM tracking_topic WHERE id=? FOR UPDATE",String.class,id(topicId)).isEmpty())
            throw new TrackingException("TOPIC_NOT_FOUND",404);
    }
    public Page<Topic> list(int page,int size) {
        paging(page,size);
        var rows=jdbc.query("SELECT * FROM tracking_topic ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?",this::topic,size+1,(long)page*size);
        return new Page<>(List.copyOf(rows.subList(0,Math.min(size,rows.size()))),page,size,rows.size()>size);
    }
    static void paging(int page,int size) {
        if(page<0 || page>10000 || size<1 || size>100) throw new TrackingException("INVALID_QUERY",400);
    }
    @Transactional
    public Topic create(Config config,String requestKey) {
        key(requestKey); config(config);
        String json=mapper.writeValueAsString(config);
        var prior=jdbc.queryForList("SELECT id FROM tracking_topic WHERE request_key=?",String.class,requestKey);
        if(!prior.isEmpty()) {
            String original=jdbc.queryForObject("SELECT creation_json FROM tracking_topic WHERE id=?",String.class,prior.getFirst());
            if(!json.equals(original)) throw new TrackingException("IDEMPOTENCY_CONFLICT",409);
            return get(prior.getFirst());
        }
        if(jdbc.queryForObject("SELECT COUNT(*) FROM tracking_topic",Integer.class)>=100)
            throw new TrackingException("TOPIC_LIMIT",409);
        long now=System.currentTimeMillis(); String topicId=uuid();
        jdbc.update("INSERT INTO tracking_topic(id,name,question,language,research_mode,status,version,schedule_minutes,next_due_at,created_at,updated_at,request_key,creation_json) VALUES (?,?,?,?,?,'ACTIVE',1,?,?,?,?,?,?)",
            topicId,config.name(),config.question(),config.language(),config.researchMode(),config.scheduleMinutes(),
            config.scheduleMinutes()==0?null:now+config.scheduleMinutes()*60000L,now,now,requestKey,json);
        jdbc.update("INSERT INTO tracking_config(topic_id,version,config_json,created_at) VALUES (?,1,?,?)",topicId,json,now);
        return get(topicId);
    }
    @Transactional
    public Topic update(String topicId,int expectedVersion,Config config,String state) {
        config(config); lock(topicId); Topic old=get(topicId);
        if(old.version()!=expectedVersion) throw new TrackingException("TOPIC_VERSION_CONFLICT",409);
        if(!Set.of("ACTIVE","PAUSED","ARCHIVED").contains(state)) throw new TrackingException("INVALID_TOPIC_STATE",400);
        if(!jdbc.queryForList("SELECT id FROM tracking_cycle WHERE topic_id=? AND status='PENDING'",String.class,old.id()).isEmpty()
            && (!old.question().equals(config.question()) || !old.language().equals(config.language()) || !old.researchMode().equals(config.researchMode())))
            throw new TrackingException("TOPIC_BUSY",409);
        long now=System.currentTimeMillis(); int version=old.version()+1;
        jdbc.update("UPDATE tracking_topic SET name=?,question=?,language=?,research_mode=?,status=?,version=?,schedule_minutes=?,next_due_at=?,updated_at=? WHERE id=?",
            config.name(),config.question(),config.language(),config.researchMode(),state,version,config.scheduleMinutes(),
            config.scheduleMinutes()==0 || !state.equals("ACTIVE")?null:now+config.scheduleMinutes()*60000L,now,old.id());
        jdbc.update("INSERT INTO tracking_config(topic_id,version,config_json,created_at) VALUES (?,?,?,?)",old.id(),version,mapper.writeValueAsString(config),now);
        return get(old.id());
    }
    @Transactional
    public Cycle check(String topicId,String requestKey) {
        key(requestKey); lock(topicId); Topic topic=get(topicId);
        String slot="manual:"+requestKey;
        var existing=jdbc.query("SELECT * FROM tracking_cycle WHERE topic_id=? AND slot_key=?",this::cycle,topic.id(),slot);
        if(!existing.isEmpty()) return existing.getFirst();
        if(!topic.status().equals("ACTIVE")) throw new TrackingException("TOPIC_NOT_ACTIVE",409);
        return enqueue(topic,slot,"MANUAL",0);
    }
    private Cycle enqueue(Topic topic,String slot,String trigger,int missed) {
        if(!jdbc.queryForList("SELECT id FROM tracking_cycle WHERE topic_id=? AND status='PENDING'",String.class,topic.id()).isEmpty())
            throw new TrackingException("TOPIC_BUSY",409);
        if(jdbc.queryForObject("SELECT COUNT(*) FROM research_task WHERE status IN ('PENDING','RUNNING')",Integer.class)>=50)
            throw new TrackingException("RESEARCH_QUEUE_FULL",409);
        var baseline=jdbc.queryForList("SELECT cy.id FROM tracking_cycle cy JOIN research_task t ON t.id=cy.task_id WHERE cy.topic_id=? AND t.question=? AND t.search_language=? AND t.research_mode=? AND cy.status='COMPLETED' ORDER BY cy.completed_at DESC,cy.id DESC LIMIT 1",
            String.class,topic.id(),topic.question(),topic.language(),topic.researchMode());
        String cycleId=uuid();
        var task=research.create(topic.question(),"tracking:"+cycleId,topic.language(),topic.researchMode());
        jdbc.update("INSERT INTO tracking_cycle(id,topic_id,config_version,slot_key,trigger_kind,task_id,baseline_cycle_id,status,created_at,missed_slots) VALUES (?,?,?,?,?,?,?,'PENDING',?,?)",
            cycleId,topic.id(),topic.version(),slot,trigger,task.id(),baseline.isEmpty()?null:baseline.getFirst(),System.currentTimeMillis(),missed);
        return getCycle(topic.id(),cycleId);
    }
    public Cycle getCycle(String topicId,String cycleId) {
        get(topicId);
        return jdbc.query("SELECT * FROM tracking_cycle WHERE topic_id=? AND id=?",this::cycle,id(topicId),id(cycleId))
            .stream().findFirst().orElseThrow(()->new TrackingException("CYCLE_NOT_FOUND",404));
    }
    public Page<Cycle> cycles(String topicId,int page,int size) {
        get(topicId); paging(page,size);
        var rows=jdbc.query("SELECT * FROM tracking_cycle WHERE topic_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            this::cycle,id(topicId),size+1,(long)page*size);
        return new Page<>(List.copyOf(rows.subList(0,Math.min(size,rows.size()))),page,size,rows.size()>size);
    }
    public Config configuration(String topicId,int version) {
        get(topicId);
        var rows=jdbc.queryForList("SELECT config_json FROM tracking_config WHERE topic_id=? AND version=?",String.class,id(topicId),version);
        if(rows.isEmpty()) throw new TrackingException("CONFIG_NOT_FOUND",404);
        return mapper.readValue(rows.getFirst(),Config.class);
    }
    public Page<Change> changes(String topicId,int page,int size) {
        get(topicId); paging(page,size);
        var rows=jdbc.query("""
            SELECT c.*,cy.task_id,s.canonical_url,r.title,r.run_id,r.evidence_json,old.evidence_json AS previous_evidence FROM tracking_change c
            JOIN tracked_source s ON s.id=c.source_id JOIN source_revision r ON r.id=c.revision_id
            JOIN tracking_cycle cy ON cy.id=c.cycle_id LEFT JOIN source_revision old ON old.id=c.previous_revision_id
            WHERE s.topic_id=? ORDER BY c.discovered_at DESC,c.id DESC LIMIT ? OFFSET ?
            """,(r,i)->new Change(r.getString("id"),r.getString("cycle_id"),r.getString("task_id"),r.getString("kind"),
                r.getBoolean("possible_duplicate"),r.getString("canonical_url"),r.getString("title"),r.getString("run_id"),
                r.getString("revision_id"),r.getString("previous_revision_id"),time(r,"discovered_at"),
                mapper.readValue(r.getString("evidence_json"),new TypeReference<List<WebReport.Passage>>(){}),
                r.getString("previous_evidence")==null?List.of():mapper.readValue(r.getString("previous_evidence"),new TypeReference<List<WebReport.Passage>>(){})),id(topicId),size+1,(long)page*size);
        return new Page<>(List.copyOf(rows.subList(0,Math.min(size,rows.size()))),page,size,rows.size()>size);
    }
    public List<String> pending() {
        return jdbc.queryForList("SELECT id FROM tracking_cycle WHERE status='PENDING' ORDER BY created_at,id LIMIT 20",String.class);
    }
    public Cycle forTask(String taskId) {
        return jdbc.query("SELECT * FROM tracking_cycle WHERE task_id=?",this::cycle,id(taskId)).stream().findFirst().orElse(null);
    }
    @Transactional
    public void reconcile(String cycleId) {
        var rows=jdbc.query("SELECT * FROM tracking_cycle WHERE id=?",this::cycle,id(cycleId));
        if(rows.isEmpty()) return;
        Cycle initial=rows.getFirst(); lock(initial.topicId());
        Cycle cycle=getCycle(initial.topicId(),cycleId);
        if(!cycle.status().equals("PENDING")) return;
        ResearchTask task=research.find(cycle.taskId()).orElseThrow();
        if(task.status()==ResearchTask.Status.PENDING || task.status()==ResearchTask.Status.RUNNING) return;
        WebReport.Outcome outcome=task.webResult()!=null?task.webResult().outcome():
            task.modelSession()!=null?task.modelSession().session().outcome():null;
        String state=task.status()==ResearchTask.Status.FAILED?"FAILED":
            outcome==null || outcome.evidence().isEmpty()?"EMPTY":"COMPLETED";
        long now=System.currentTimeMillis();
        // Failed runs retain evidence in their research snapshot but do not alter the baseline.
        Set<String> resolved=new HashSet<>();
        if(state.equals("COMPLETED")) for(var source:outcome.sources()) {
            if(!"READ".equals(source.status()) || source.metadata()==null) continue;
            var passages=outcome.evidence().stream().filter(e->e.sourceId().equals(source.candidate().sourceId())).toList();
            if(passages.isEmpty()) continue;
            if(!resolved.add(source.metadata().resolvedUrl())) continue;
            saveSource(cycle,task.runId(),source,passages,now);
        }
        jdbc.update("UPDATE tracking_cycle SET status=?,run_id=?,error_code=?,completed_at=? WHERE id=? AND status='PENDING'",
            state,task.runId(),state.equals("FAILED")?task.errorCode():state.equals("EMPTY")?"NO_USABLE_EVIDENCE":null,now,cycle.id());
    }
    private void saveSource(Cycle cycle,String runId,WebReport.Source source,List<WebReport.Passage> passages,long now) {
        String url=source.metadata().resolvedUrl(); String hash=sha(url);
        var ids=jdbc.queryForList("SELECT id FROM tracked_source WHERE topic_id=? AND url_hash=?",String.class,cycle.topicId(),hash);
        String sourceId;
        if(ids.isEmpty()) {
            sourceId=uuid();
            jdbc.update("INSERT INTO tracked_source(id,topic_id,url_hash,canonical_url,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?)",
                sourceId,cycle.topicId(),hash,url,now,now);
        } else {
            sourceId=ids.getFirst();
            if(!url.equals(jdbc.queryForObject("SELECT canonical_url FROM tracked_source WHERE id=?",String.class,sourceId)))
                throw new TrackingException("SOURCE_HASH_CONFLICT",409);
            jdbc.update("UPDATE tracked_source SET last_seen_at=? WHERE id=?",now,sourceId);
        }
        String extraction=source.metadata().extractor()+":"+source.metadata().normalizationVersion();
        var previous=jdbc.queryForList("""
            SELECT r.id,r.content_hash,r.extraction_version FROM source_revision r
            JOIN tracking_change ch ON ch.revision_id=r.id JOIN tracking_cycle cy ON cy.id=ch.cycle_id
            JOIN research_task t ON t.id=cy.task_id
            WHERE r.source_id=? AND t.question=? AND t.search_language=? AND t.research_mode=?
            ORDER BY ch.discovered_at DESC,ch.id DESC LIMIT 1
            """,sourceId,configuration(cycle.topicId(),cycle.configVersion()).question(),
                configuration(cycle.topicId(),cycle.configVersion()).language(),configuration(cycle.topicId(),cycle.configVersion()).researchMode());
        String prior=previous.isEmpty()?null:(String)previous.getFirst().get("id");
        String kind=prior==null?"FIRST_SEEN":!extraction.equals(previous.getFirst().get("extraction_version"))?"EXTRACTOR_CHANGED":
            source.metadata().extractedTextHash().equals(previous.getFirst().get("content_hash"))?"UNCHANGED":"UPDATED";
        String revision=uuid();
        jdbc.update("INSERT INTO source_revision(id,source_id,run_id,content_hash,extraction_version,title,evidence_json,retrieved_at) VALUES (?,?,?,?,?,?,?,?)",
            revision,sourceId,runId,source.metadata().extractedTextHash(),extraction,source.candidate().title(),mapper.writeValueAsString(passages),now);
        boolean duplicate=jdbc.queryForObject("""
            SELECT COUNT(*) FROM source_revision r JOIN tracked_source s ON s.id=r.source_id
            WHERE s.topic_id=? AND s.id<>? AND r.content_hash=? AND r.extraction_version=?
            """,Integer.class,cycle.topicId(),sourceId,source.metadata().extractedTextHash(),extraction)>0;
        jdbc.update("INSERT INTO tracking_change(id,cycle_id,source_id,revision_id,previous_revision_id,kind,possible_duplicate,discovered_at) VALUES (?,?,?,?,?,?,?,?)",
            uuid(),cycle.id(),sourceId,revision,prior,kind,duplicate,now);
    }
    static String sha(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch(java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }

    @Transactional
    public Cycle retry(String topicId,String cycleId,String failedRunId) {
        lock(topicId); Cycle cycle=getCycle(topicId,cycleId);
        if(!Set.of("FAILED","PENDING").contains(cycle.status())) throw new TrackingException("CYCLE_RETRY_CONFLICT",409);
        if(cycle.status().equals("FAILED")) {
            Topic topic=get(topicId);
            if(!topic.status().equals("ACTIVE")) throw new TrackingException("TOPIC_NOT_ACTIVE",409);
            Config original=configuration(topicId,cycle.configVersion());
            if(!topic.question().equals(original.question()) || !topic.language().equals(original.language()) || !topic.researchMode().equals(original.researchMode()))
                throw new TrackingException("CYCLE_RETRY_CONFLICT",409);
            if(!cycles(topicId,0,1).items().getFirst().id().equals(cycle.id())) throw new TrackingException("CYCLE_RETRY_CONFLICT",409);
        }
        research.retry(cycle.taskId(),id(failedRunId));
        jdbc.update("UPDATE tracking_cycle SET status='PENDING',completed_at=NULL,error_code=NULL WHERE id=?",cycle.id());
        return getCycle(topicId,cycleId);
    }

    public List<String> due(long now) {
        return jdbc.queryForList("SELECT id FROM tracking_topic WHERE status='ACTIVE' AND next_due_at<=? ORDER BY next_due_at,id LIMIT 10",String.class,now);
    }
    @Transactional
    public void schedule(String topicId,long now) {
        lock(topicId); Topic topic=get(topicId);
        if(!topic.status().equals("ACTIVE") || topic.scheduleMinutes()==0 || topic.nextDueAt()==null || topic.nextDueAt().toEpochMilli()>now) return;
        if(!topic.researchMode().equals("web")) throw new TrackingException("INVALID_TRACKING_SCHEDULE",400);
        long period=topic.scheduleMinutes()*60000L;
        long due=topic.nextDueAt().toEpochMilli(); long slots=(now-due)/period;
        // Busy topics advance their clock instead of accumulating unbounded work.
        if(jdbc.queryForObject("SELECT COUNT(*) FROM tracking_cycle WHERE topic_id=? AND status='PENDING'",Integer.class,topic.id())==0) {
            enqueue(topic,"scheduled:"+topic.version()+":"+due,"SCHEDULED",(int)Math.min(slots,Integer.MAX_VALUE));
        }
        jdbc.update("UPDATE tracking_topic SET next_due_at=? WHERE id=?",due+(slots+1)*period,topic.id());
    }
}
