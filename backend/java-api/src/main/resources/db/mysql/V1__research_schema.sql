-- MySQL 8.4, independent migration history from H2. No automatic data transfer.
-- NO PAD / case-sensitive collation preserves exact idempotency key identity.
CREATE TABLE research_task (
    id VARCHAR(36) PRIMARY KEY,
    question VARCHAR(4000) NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    status VARCHAR(16) NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    INDEX idx_research_task_pending (status, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE research_run (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL UNIQUE,
    status VARCHAR(16) NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    started_at BIGINT NOT NULL,
    completed_at BIGINT,
    answer MEDIUMTEXT,
    sources_json MEDIUMTEXT,
    error_code VARCHAR(64),
    report_provider VARCHAR(80),
    search_query VARCHAR(4000),
    retrieved_at BIGINT,
    generation_json MEDIUMTEXT,
    CONSTRAINT fk_run_task FOREIGN KEY (task_id) REFERENCES research_task(id),
    CHECK (
        (status = 'RUNNING' AND completed_at IS NULL AND answer IS NULL AND sources_json IS NULL AND error_code IS NULL)
        OR (status = 'SUCCEEDED' AND completed_at IS NOT NULL AND answer IS NOT NULL AND sources_json IS NOT NULL AND error_code IS NULL)
        OR (status = 'FAILED' AND completed_at IS NOT NULL AND answer IS NULL AND sources_json IS NULL AND error_code IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE research_evidence (
    run_id VARCHAR(36) NOT NULL,
    evidence_id VARCHAR(32) NOT NULL,
    position INTEGER NOT NULL,
    url VARCHAR(2048) NOT NULL,
    title VARCHAR(512) NOT NULL,
    excerpt VARCHAR(1600) NOT NULL,
    retrieved_at BIGINT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (run_id, evidence_id),
    UNIQUE (run_id, position),
    CONSTRAINT fk_evidence_run FOREIGN KEY (run_id) REFERENCES research_run(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
