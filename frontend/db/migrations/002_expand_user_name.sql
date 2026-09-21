ALTER TABLE users DROP CONSTRAINT users_name_check;

ALTER TABLE users
    ALTER COLUMN name TYPE varchar(256),
    ADD CONSTRAINT users_name_check CHECK (char_length(name) BETWEEN 1 AND 256);
