ALTER TABLE machines
    DROP CONSTRAINT IF EXISTS machines_status_check;

ALTER TABLE machines
    ADD CONSTRAINT machines_status_check CHECK (
        status IN ('created', 'building', 'ready', 'failed', 'cancelled', 'preparing', 'deleted')
    );

ALTER TABLE chat_sessions
    DROP CONSTRAINT IF EXISTS chat_sessions_creation_status_check;

ALTER TABLE chat_sessions
    ADD CONSTRAINT chat_sessions_creation_status_check CHECK (
        creation_status IN (
            'input', 'generating_scenario', 'building', 'completed', 'failed', 'cancelled'
        )
    );

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS creation_failure jsonb;

ALTER TABLE chat_sessions
    DROP CONSTRAINT IF EXISTS chat_sessions_creation_failure_check;

ALTER TABLE chat_sessions
    ADD CONSTRAINT chat_sessions_creation_failure_check CHECK (
        creation_failure IS NULL OR jsonb_typeof(creation_failure) = 'object'
    );
