ALTER TABLE skill_versions
    ADD COLUMN IF NOT EXISTS reference_documents jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE session_skill_snapshot_items
    ADD COLUMN IF NOT EXISTS selected_reference_ids jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE scenario_versions ALTER COLUMN target_os SET DEFAULT 'Debian 13.7.0';
