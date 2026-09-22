-- The legacy table only recorded "at least one flag solved". Preserve the exact
-- history where it can be inferred unambiguously from single-flag machines.
INSERT INTO machine_flag_solutions (user_id, machine_id, flag_kind, solved_at)
SELECT
    solutions.user_id,
    solutions.machine_id,
    CASE WHEN machines.user_flag <> '' THEN 'user' ELSE 'system' END,
    solutions.solved_at
FROM machine_solutions AS solutions
JOIN machines ON machines.id = solutions.machine_id
WHERE (machines.user_flag <> '') <> (machines.system_flag <> '')
ON CONFLICT (user_id, machine_id, flag_kind) DO NOTHING;
