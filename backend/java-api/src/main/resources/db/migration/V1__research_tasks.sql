CREATE TABLE research_task (
    id VARCHAR(36) PRIMARY KEY,
    question VARCHAR(4000) NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    status VARCHAR(16) NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

CREATE INDEX idx_research_task_pending ON research_task(status, created_at, id);

-- Only one execution per task in this milestone. Retry requires a new design/migration.
CREATE TABLE research_run (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL UNIQUE REFERENCES research_task(id),
    status VARCHAR(16) NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    started_at BIGINT NOT NULL,
    completed_at BIGINT,
    answer CLOB,
    sources_json CLOB,
    error_code VARCHAR(64),
    CHECK (
        (status = 'RUNNING' AND completed_at IS NULL AND answer IS NULL AND sources_json IS NULL AND error_code IS NULL)
        OR (status = 'SUCCEEDED' AND completed_at IS NOT NULL AND answer IS NOT NULL AND sources_json IS NOT NULL AND error_code IS NULL)
        OR (status = 'FAILED' AND completed_at IS NOT NULL AND answer IS NULL AND sources_json IS NULL AND error_code IS NOT NULL)
    )
);
