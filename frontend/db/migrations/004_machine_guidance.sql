CREATE TABLE machine_flag_solutions (
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    machine_id varchar(128) NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    flag_kind varchar(6) NOT NULL CHECK (flag_kind IN ('user', 'system')),
    solved_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, machine_id, flag_kind)
);

CREATE INDEX machine_flag_solutions_machine_idx
    ON machine_flag_solutions (machine_id, user_id);

CREATE TABLE machine_guidance (
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    machine_id varchar(128) NOT NULL REFERENCES machines(id) ON DELETE RESTRICT,
    content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
    generation integer NOT NULL DEFAULT 1 CHECK (generation > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, machine_id)
);
