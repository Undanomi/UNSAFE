CREATE TABLE IF NOT EXISTS skills (
    skill_id uuid PRIMARY KEY,
    name varchar(64) NOT NULL UNIQUE,
    description text NOT NULL,
    status varchar(16) NOT NULL CHECK (status IN ('draft', 'active', 'disabled')),
    current_version integer,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_versions (
    skill_id uuid NOT NULL REFERENCES skills(skill_id),
    version integer NOT NULL CHECK (version > 0),
    instructions text NOT NULL,
    phases jsonb NOT NULL,
    selectors jsonb NOT NULL,
    priority integer NOT NULL DEFAULT 100,
    content_checksum char(64) NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    published_at timestamptz,
    PRIMARY KEY (skill_id, version)
);

CREATE TABLE IF NOT EXISTS session_skill_snapshots (
    session_id uuid NOT NULL REFERENCES ai_sessions(session_id) ON DELETE CASCADE,
    phase varchar(32) NOT NULL,
    resolved_at timestamptz NOT NULL,
    PRIMARY KEY (session_id, phase)
);

CREATE TABLE IF NOT EXISTS session_skill_snapshot_items (
    session_id uuid NOT NULL,
    phase varchar(32) NOT NULL,
    skill_id uuid NOT NULL,
    skill_version integer NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    selection_reason text NOT NULL,
    content_checksum char(64) NOT NULL,
    PRIMARY KEY (session_id, phase, skill_id),
    UNIQUE (session_id, phase, position),
    FOREIGN KEY (session_id, phase)
        REFERENCES session_skill_snapshots(session_id, phase) ON DELETE CASCADE,
    FOREIGN KEY (skill_id, skill_version)
        REFERENCES skill_versions(skill_id, version)
);

CREATE INDEX IF NOT EXISTS skills_status_idx ON skills (status);
CREATE INDEX IF NOT EXISTS skill_snapshot_items_version_idx
    ON session_skill_snapshot_items (skill_id, skill_version);
