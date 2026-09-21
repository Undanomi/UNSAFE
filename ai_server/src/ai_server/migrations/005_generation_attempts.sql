ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS scenario_generation_attempts integer NOT NULL DEFAULT 0
    CHECK (scenario_generation_attempts >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS scenario_generation_attempt_limit integer NOT NULL DEFAULT 0
    CHECK (scenario_generation_attempt_limit >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS source_generation_attempts integer NOT NULL DEFAULT 0
    CHECK (source_generation_attempts >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS source_generation_attempt_limit integer NOT NULL DEFAULT 0
    CHECK (source_generation_attempt_limit >= 0);
