CREATE TABLE IF NOT EXISTS build_jobs (
    build_id uuid PRIMARY KEY,
    scenario_id text NOT NULL,
    scenario_version_id text NOT NULL,
    requested_by text NOT NULL,
    idempotency_key text NOT NULL,
    status text NOT NULL,
    progress integer NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    worker_id text,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    error_message text,
    machine_password text,
    cancel_requested boolean NOT NULL DEFAULT false,
    UNIQUE (requested_by, idempotency_key)
);

CREATE INDEX IF NOT EXISTS build_jobs_queue_idx
    ON build_jobs (queued_at)
    WHERE status IN ('queued', 'retrying');

CREATE TABLE IF NOT EXISTS build_events (
    build_event_id bigserial PRIMARY KEY,
    build_id uuid NOT NULL REFERENCES build_jobs(build_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    message text NOT NULL,
    progress integer NOT NULL CHECK (progress BETWEEN 0 AND 100),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS build_events_build_idx
    ON build_events (build_id, build_event_id);

CREATE TABLE IF NOT EXISTS build_artifacts (
    artifact_id uuid PRIMARY KEY,
    build_id uuid NOT NULL REFERENCES build_jobs(build_id) ON DELETE CASCADE,
    artifact_type text NOT NULL,
    file_name text NOT NULL,
    file_size bigint NOT NULL,
    checksum text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (build_id, file_name)
);

ALTER TABLE build_jobs
    ADD COLUMN IF NOT EXISTS machine_password text;
