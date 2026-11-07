CREATE TABLE research_execution_control (
    run_id VARCHAR(36) PRIMARY KEY REFERENCES research_run(id),
    stage VARCHAR(32) NOT NULL,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    reused INTEGER NOT NULL DEFAULT 0,
    updated_at BIGINT NOT NULL
);
