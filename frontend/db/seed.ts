import process from "node:process"
import { Pool } from "pg"
import { SEED_MACHINES, SEED_SOLUTIONS, SEED_USERS } from "./seed/data"

const DEVELOPMENT_DATABASE_NAME = "frontend_service"
const DEVELOPMENT_DATABASE_HOSTS = new Set([
  "frontend-postgres",
  "localhost",
  "127.0.0.1",
  "::1",
  "[::1]",
])

function developmentDatabaseUrl(): string {
  if (process.env.NODE_ENV === "production") {
    throw new Error("Seed data cannot be applied in production.")
  }

  const value = process.env.DATABASE_URL
  if (!value) throw new Error("DATABASE_URL is not configured.")

  const url = new URL(value)
  const databaseName = decodeURIComponent(url.pathname.replace(/^\//, ""))
  if (!DEVELOPMENT_DATABASE_HOSTS.has(url.hostname) || databaseName !== DEVELOPMENT_DATABASE_NAME) {
    throw new Error(
      `Seed data can only be applied to the local ${DEVELOPMENT_DATABASE_NAME} database.`,
    )
  }

  return value
}

async function main() {
  const pool = new Pool({ connectionString: developmentDatabaseUrl(), max: 1 })
  const client = await pool.connect()

  try {
    await client.query("BEGIN")

    for (const user of SEED_USERS) {
      await client.query(
        `INSERT INTO users
          (id, name, bio, icon_url, theme, profile_completed, created_at, updated_at)
         VALUES ($1, $2, $3, '', $4, true, $5, $5)
         ON CONFLICT (id) DO UPDATE SET
           name = EXCLUDED.name,
           bio = EXCLUDED.bio,
           icon_url = EXCLUDED.icon_url,
           theme = EXCLUDED.theme,
           profile_completed = EXCLUDED.profile_completed,
           created_at = EXCLUDED.created_at,
           updated_at = now()`,
        [user.id, user.name, user.bio, user.theme, user.createdAt],
      )
    }

    for (const machine of SEED_MACHINES) {
      await client.query(
        `INSERT INTO machines
          (id, created_by, ai_session_id, name, summary, description, file_path, level,
           published, status, build_progress, system_flag, user_flag, tags, created_at, updated_at)
         VALUES ($1, $2, NULL, $3, $4, $5, '', $6, true, 'ready', 100, $7, $8, $9, $10, $10)
         ON CONFLICT (id) DO UPDATE SET
           created_by = EXCLUDED.created_by,
           ai_session_id = EXCLUDED.ai_session_id,
           name = EXCLUDED.name,
           summary = EXCLUDED.summary,
           description = EXCLUDED.description,
           file_path = EXCLUDED.file_path,
           level = EXCLUDED.level,
           published = EXCLUDED.published,
           status = EXCLUDED.status,
           build_progress = EXCLUDED.build_progress,
           system_flag = EXCLUDED.system_flag,
           user_flag = EXCLUDED.user_flag,
           tags = EXCLUDED.tags,
           error_message = NULL,
           created_at = EXCLUDED.created_at,
           updated_at = now()`,
        [
          machine.id,
          machine.createdBy,
          machine.name,
          machine.summary,
          machine.description,
          machine.level,
          machine.systemFlag,
          machine.userFlag,
          machine.tags,
          machine.createdAt,
        ],
      )
    }

    for (const solution of SEED_SOLUTIONS) {
      await client.query(
        `INSERT INTO machine_solutions (user_id, machine_id, solved_at)
         VALUES ($1, $2, $3)
         ON CONFLICT (user_id, machine_id) DO UPDATE SET
           solved_at = EXCLUDED.solved_at`,
        [solution.userId, solution.machineId, solution.solvedAt],
      )
      await client.query(
        `INSERT INTO machine_flag_solutions (user_id, machine_id, flag_kind, solved_at)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (user_id, machine_id, flag_kind) DO UPDATE SET
           solved_at = EXCLUDED.solved_at`,
        [solution.userId, solution.machineId, solution.flagKind, solution.solvedAt],
      )
    }

    await client.query("COMMIT")
    console.log(
      `Seed data applied: ${SEED_USERS.length} users, ${SEED_MACHINES.length} machines, and ${SEED_SOLUTIONS.length} solutions.`,
    )
  } catch (error) {
    await client.query("ROLLBACK")
    throw error
  } finally {
    client.release()
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
