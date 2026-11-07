CREATE TABLE tracking_topic (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    question VARCHAR(4000) NOT NULL,
    language VARCHAR(8) NOT NULL CHECK (language IN ('en','zh')),
    research_mode VARCHAR(16) NOT NULL CHECK (research_mode IN ('web','web-model')),
    status VARCHAR(16) NOT NULL CHECK (status IN ('ACTIVE','PAUSED','ARCHIVED')),
    version INTEGER NOT NULL,
    schedule_minutes INTEGER NOT NULL DEFAULT 0,
    next_due_at BIGINT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    request_key VARCHAR(128) NOT NULL UNIQUE,
    creation_json TEXT NOT NULL,
    CHECK (schedule_minutes = 0 OR (schedule_minutes >= 60 AND schedule_minutes <= 10080)),
    CHECK (schedule_minutes = 0 OR research_mode = 'web')
);
CREATE INDEX idx_tracking_due ON tracking_topic(status,next_due_at,id);
CREATE TABLE tracking_config (
    topic_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY(topic_id,version),
    FOREIGN KEY(topic_id) REFERENCES tracking_topic(id)
);
CREATE TABLE tracking_cycle (
    id VARCHAR(36) PRIMARY KEY,
    topic_id VARCHAR(36) NOT NULL,
    config_version INTEGER NOT NULL,
    slot_key VARCHAR(160) NOT NULL,
    trigger_kind VARCHAR(16) NOT NULL CHECK(trigger_kind IN ('MANUAL','SCHEDULED')),
    task_id VARCHAR(36) NOT NULL UNIQUE,
    run_id VARCHAR(36),
    baseline_cycle_id VARCHAR(36),
    status VARCHAR(16) NOT NULL CHECK(status IN ('PENDING','COMPLETED','FAILED','EMPTY')),
    error_code VARCHAR(80),
    created_at BIGINT NOT NULL,
    completed_at BIGINT,
    missed_slots INTEGER NOT NULL DEFAULT 0,
    UNIQUE(topic_id,slot_key),
    FOREIGN KEY(topic_id,config_version) REFERENCES tracking_config(topic_id,version),
    FOREIGN KEY(task_id) REFERENCES research_task(id),
    FOREIGN KEY(run_id) REFERENCES research_run(id),
    FOREIGN KEY(baseline_cycle_id) REFERENCES tracking_cycle(id)
);
CREATE INDEX idx_tracking_cycle_topic ON tracking_cycle(topic_id,created_at,id);
CREATE INDEX idx_tracking_cycle_pending ON tracking_cycle(status,created_at,id);
CREATE TABLE tracked_source (
    id VARCHAR(36) PRIMARY KEY,
    topic_id VARCHAR(36) NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    canonical_url VARCHAR(2048) NOT NULL,
    first_seen_at BIGINT NOT NULL,
    last_seen_at BIGINT NOT NULL,
    UNIQUE(topic_id,url_hash),
    FOREIGN KEY(topic_id) REFERENCES tracking_topic(id)
);
CREATE TABLE source_revision (
    id VARCHAR(36) PRIMARY KEY,
    source_id VARCHAR(36) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    extraction_version VARCHAR(160) NOT NULL,
    title VARCHAR(512) NOT NULL,
    evidence_json TEXT NOT NULL,
    retrieved_at BIGINT NOT NULL,
    UNIQUE(source_id,run_id),
    FOREIGN KEY(source_id) REFERENCES tracked_source(id),
    FOREIGN KEY(run_id) REFERENCES research_run(id)
);
CREATE INDEX idx_source_revision_recent ON source_revision(source_id,retrieved_at,id);
CREATE TABLE tracking_change (
    id VARCHAR(36) PRIMARY KEY,
    cycle_id VARCHAR(36) NOT NULL,
    source_id VARCHAR(36) NOT NULL,
    revision_id VARCHAR(36) NOT NULL,
    previous_revision_id VARCHAR(36),
    kind VARCHAR(32) NOT NULL CHECK(kind IN ('FIRST_SEEN','UPDATED','UNCHANGED','EXTRACTOR_CHANGED')),
    possible_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
    discovered_at BIGINT NOT NULL,
    UNIQUE(cycle_id,source_id),
    FOREIGN KEY(cycle_id) REFERENCES tracking_cycle(id),
    FOREIGN KEY(source_id) REFERENCES tracked_source(id),
    FOREIGN KEY(revision_id) REFERENCES source_revision(id),
    FOREIGN KEY(previous_revision_id) REFERENCES source_revision(id)
);
CREATE INDEX idx_tracking_change_cycle ON tracking_change(cycle_id,discovered_at,id);
