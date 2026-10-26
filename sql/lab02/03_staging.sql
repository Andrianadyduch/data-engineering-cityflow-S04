CREATE TABLE IF NOT EXISTS stg.raw_records (
    staging_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL CHECK (source_row_number > 1),
    raw_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, source_file, source_row_number)
);
