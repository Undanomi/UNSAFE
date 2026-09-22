ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS scenario_sync_attempts integer NOT NULL DEFAULT 0
    CHECK (scenario_sync_attempts >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS scenario_sync_attempt_limit integer NOT NULL DEFAULT 0
    CHECK (scenario_sync_attempt_limit >= 0);
