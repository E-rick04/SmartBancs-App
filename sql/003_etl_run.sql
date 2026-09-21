CREATE TABLE IF NOT EXISTS etl_run (
    id SERIAL PRIMARY KEY,
    summary JSONB NOT NULL,
    valid_rows JSONB NOT NULL,
    rejected_rows JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    recommendation TEXT,
    model_version VARCHAR(50),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP,
    last_error VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS ix_etl_run_pending ON etl_run (status, available_at, id);
