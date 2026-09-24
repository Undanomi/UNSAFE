ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS ai_input_tokens bigint NOT NULL DEFAULT 0
    CHECK (ai_input_tokens >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS ai_output_tokens bigint NOT NULL DEFAULT 0
    CHECK (ai_output_tokens >= 0);

ALTER TABLE ai_sessions
    ADD COLUMN IF NOT EXISTS ai_total_tokens bigint NOT NULL DEFAULT 0
    CHECK (ai_total_tokens >= 0);
