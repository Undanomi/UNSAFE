CREATE TABLE IF NOT EXISTS session_skill_plans (
    session_id uuid PRIMARY KEY REFERENCES ai_sessions(session_id) ON DELETE CASCADE,
    plan jsonb NOT NULL
);

ALTER TABLE session_skill_snapshot_items
    ADD COLUMN IF NOT EXISTS selection_details jsonb NOT NULL DEFAULT '{}'::jsonb;
