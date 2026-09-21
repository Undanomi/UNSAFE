import { createHash } from "node:crypto"
import { readdir, readFile } from "node:fs/promises"
import path from "node:path"
import process from "node:process"
import { Pool } from "pg"

const MIGRATION_LOCK_ID = "694636019042026"

async function main() {
  const databaseUrl = process.env.DATABASE_URL
  if (!databaseUrl) throw new Error("DATABASE_URL is not configured.")

  const directory = path.join(process.cwd(), "db", "migrations")
  const names = (await readdir(directory)).filter((name) => name.endsWith(".sql")).sort()
  const pool = new Pool({ connectionString: databaseUrl, max: 1 })
  const client = await pool.connect()

  try {
    for (const name of names) {
      const sql = await readFile(path.join(directory, name), "utf8")
      const checksum = createHash("sha256").update(sql).digest("hex")

      await client.query("BEGIN")
      try {
        await client.query("SELECT pg_advisory_xact_lock($1)", [MIGRATION_LOCK_ID])
        await client.query(`
          CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY,
            checksum char(64) NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
          )
        `)
        const applied = await client.query<{ checksum: string }>(
          "SELECT checksum FROM schema_migrations WHERE version = $1",
          [name],
        )
        if (applied.rowCount) {
          if (applied.rows[0].checksum.trim() !== checksum) {
            throw new Error(`Applied migration ${name} has changed.`)
          }
          await client.query("COMMIT")
          continue
        }

        await client.query(sql)
        await client.query("INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)", [
          name,
          checksum,
        ])
        await client.query("COMMIT")
        console.log(`Applied ${name}`)
      } catch (error) {
        await client.query("ROLLBACK")
        throw error
      }
    }
  } finally {
    client.release()
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
