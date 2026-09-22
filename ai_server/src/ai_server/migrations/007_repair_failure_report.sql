ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS repair_failure_report jsonb;
