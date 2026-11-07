ALTER TABLE research_run ADD COLUMN report_provider VARCHAR(80);
ALTER TABLE research_run ADD COLUMN search_query VARCHAR(4000);
ALTER TABLE research_run ADD COLUMN retrieved_at BIGINT;

CREATE TABLE research_evidence (
    run_id VARCHAR(36) NOT NULL REFERENCES research_run(id),
    evidence_id VARCHAR(32) NOT NULL,
    position INTEGER NOT NULL,
    url VARCHAR(2048) NOT NULL,
    title VARCHAR(512) NOT NULL,
    excerpt VARCHAR(1600) NOT NULL,
    retrieved_at BIGINT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (run_id, evidence_id),
    UNIQUE (run_id, position)
);
