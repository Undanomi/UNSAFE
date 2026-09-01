CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id varchar(128) PRIMARY KEY,
    owner_user_id text NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    difficulty text NOT NULL,
    status text NOT NULL,
    current_version integer NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_versions (
    scenario_version_id varchar(128) NOT NULL,
    scenario_id varchar(128) NOT NULL REFERENCES scenarios(scenario_id),
    version integer NOT NULL,
    scenario_definition text NOT NULL,
    target_os text NOT NULL DEFAULT 'Ubuntu 26.04',
    attack_graph jsonb NOT NULL,
    generated_code_path text,
    generated_code_checksum char(64),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (scenario_id, scenario_version_id)
);

CREATE TABLE IF NOT EXISTS ai_sessions (
    session_id uuid PRIMARY KEY,
    owner_user_id text NOT NULL,
    status text NOT NULL,
    machine_information jsonb,
    scenario_id varchar(128) REFERENCES scenarios(scenario_id),
    scenario_version_id varchar(128),
    generated_code_path text,
    generated_code_checksum char(64),
    build_id uuid,
    build_status text,
    build_progress integer NOT NULL DEFAULT 0 CHECK (build_progress BETWEEN 0 AND 100),
    build_repair_attempts integer NOT NULL DEFAULT 0 CHECK (build_repair_attempts >= 0),
    machine_access jsonb,
    artifact jsonb,
    error_message text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ai_sessions_owner_updated_idx
    ON ai_sessions (owner_user_id, updated_at DESC);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS build_repair_attempts integer NOT NULL DEFAULT 0
    CHECK (build_repair_attempts >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS machine_access jsonb;

DROP TABLE IF EXISTS generation_jobs;
