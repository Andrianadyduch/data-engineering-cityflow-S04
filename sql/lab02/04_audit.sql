CREATE TABLE IF NOT EXISTS audit.load_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (
        status IN ('running', 'success', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS load_runs_batch_id_idx
ON audit.load_runs(batch_id);

CREATE TABLE IF NOT EXISTS audit.file_stats (
    run_id BIGINT NOT NULL REFERENCES audit.load_runs(run_id),
    source_file TEXT NOT NULL,
    input_count INTEGER NOT NULL CHECK (input_count >= 0),
    accepted_count INTEGER NOT NULL CHECK (accepted_count >= 0),
    rejected_count INTEGER NOT NULL CHECK (rejected_count >= 0),
    duplicate_count INTEGER NOT NULL CHECK (duplicate_count >= 0),
    PRIMARY KEY (run_id, source_file),
    CHECK (
        input_count = accepted_count + rejected_count + duplicate_count
    )
);

CREATE TABLE IF NOT EXISTS audit.row_results (
    result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES audit.load_runs(run_id),
    batch_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    business_key TEXT,
    row_status TEXT NOT NULL CHECK (
        row_status IN ('accepted', 'rejected', 'duplicate')
    ),
    reason_code TEXT,
    reason TEXT,
    raw_payload JSONB NOT NULL,
    UNIQUE (run_id, source_file, source_row_number)
);
