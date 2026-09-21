CREATE TABLE users (
    id varchar(128) PRIMARY KEY,
    name varchar(30) NOT NULL CHECK (char_length(name) BETWEEN 1 AND 30),
    bio varchar(500) NOT NULL DEFAULT '',
    icon_url varchar(2048) NOT NULL DEFAULT '',
    theme varchar(5) NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark')),
    profile_completed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE machines (
    id varchar(128) PRIMARY KEY,
    created_by varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    ai_session_id varchar(128) UNIQUE,
    name varchar(40) NOT NULL CHECK (char_length(name) BETWEEN 1 AND 40),
    summary text NOT NULL DEFAULT '',
    description text NOT NULL DEFAULT '',
    file_path text NOT NULL DEFAULT '',
    level varchar(6) NOT NULL CHECK (level IN ('easy', 'medium', 'hard')),
    published boolean NOT NULL DEFAULT false,
    status varchar(10) NOT NULL CHECK (
        status IN ('created', 'building', 'ready', 'failed', 'preparing', 'deleted')
    ),
    build_progress integer NOT NULL DEFAULT 0 CHECK (build_progress BETWEEN 0 AND 100),
    system_flag varchar(200) NOT NULL DEFAULT '',
    user_flag varchar(200) NOT NULL DEFAULT '',
    tags text[] NOT NULL DEFAULT '{}',
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chat_sessions (
    ai_session_id varchar(128) PRIMARY KEY,
    owner_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name varchar(40) NOT NULL CHECK (char_length(name) BETWEEN 1 AND 40),
    current_step integer NOT NULL CHECK (current_step BETWEEN 1 AND 9),
    basic_ready boolean NOT NULL DEFAULT false,
    answers jsonb NOT NULL CHECK (jsonb_typeof(answers) = 'object'),
    creation_status varchar(20) NOT NULL DEFAULT 'input' CHECK (
        creation_status IN ('input', 'generating_scenario', 'building', 'completed', 'failed')
    ),
    machine_id varchar(128) UNIQUE REFERENCES machines(id) ON DELETE RESTRICT,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE machine_solutions (
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    machine_id varchar(128) NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    solved_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, machine_id)
);

CREATE INDEX machines_created_by_created_at_idx
    ON machines (created_by, created_at DESC);
CREATE INDEX machines_visibility_created_at_idx
    ON machines (published, status, created_at DESC);
CREATE INDEX chat_sessions_owner_updated_idx
    ON chat_sessions (owner_user_id, updated_at DESC);
CREATE INDEX machine_solutions_machine_idx
    ON machine_solutions (machine_id, user_id);
