ALTER TABLE machines
    ALTER COLUMN level TYPE varchar(9);

ALTER TABLE machines
    DROP CONSTRAINT IF EXISTS machines_level_check;

ALTER TABLE machines
    ADD CONSTRAINT machines_level_check CHECK (
        level IN ('very_easy', 'easy', 'medium', 'hard')
    );
