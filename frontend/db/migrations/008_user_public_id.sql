ALTER TABLE users
    ADD COLUMN public_id uuid NOT NULL DEFAULT gen_random_uuid(),
    ADD CONSTRAINT users_public_id_key UNIQUE (public_id);
