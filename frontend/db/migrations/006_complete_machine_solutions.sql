-- A machine is solved only after every flag it contains has been acquired by
-- someone other than its creator. Rebuild legacy first-flag records accordingly.
CREATE TEMP TABLE completed_machine_solutions ON COMMIT DROP AS
SELECT
    fs.user_id,
    fs.machine_id,
    MAX(fs.solved_at) AS solved_at
FROM machine_flag_solutions AS fs
JOIN machines AS m ON m.id = fs.machine_id
WHERE fs.user_id <> m.created_by
    AND (
        (fs.flag_kind = 'user' AND m.user_flag <> '')
        OR (fs.flag_kind = 'system' AND m.system_flag <> '')
    )
GROUP BY fs.user_id, fs.machine_id, m.user_flag, m.system_flag
HAVING COUNT(*) = (m.user_flag <> '')::integer + (m.system_flag <> '')::integer;

DELETE FROM machine_solutions AS s
WHERE NOT EXISTS (
    SELECT 1
    FROM completed_machine_solutions AS completed
    WHERE completed.user_id = s.user_id
        AND completed.machine_id = s.machine_id
);

INSERT INTO machine_solutions (user_id, machine_id, solved_at)
SELECT user_id, machine_id, solved_at
FROM completed_machine_solutions
ON CONFLICT (user_id, machine_id) DO UPDATE SET
    solved_at = EXCLUDED.solved_at;
