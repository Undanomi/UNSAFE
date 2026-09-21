import "server-only"

import { Pool, type PoolClient, type QueryResultRow } from "pg"

declare global {
  var slsgPostgresPool: Pool | undefined
}

function databaseUrl(): string {
  const value = process.env.DATABASE_URL
  if (!value) throw new Error("DATABASE_URL is not configured.")
  return value
}

export function getDatabasePool(): Pool {
  if (!globalThis.slsgPostgresPool) {
    globalThis.slsgPostgresPool = new Pool({
      connectionString: databaseUrl(),
      max: 10,
      connectionTimeoutMillis: 5_000,
      idleTimeoutMillis: 30_000,
    })
  }
  return globalThis.slsgPostgresPool
}

export async function queryDatabase<Row extends QueryResultRow>(
  text: string,
  values: readonly unknown[] = [],
) {
  return getDatabasePool().query<Row>(text, [...values])
}

export async function withDatabaseTransaction<T>(
  operation: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await getDatabasePool().connect()
  try {
    await client.query("BEGIN")
    const result = await operation(client)
    await client.query("COMMIT")
    return result
  } catch (error) {
    await client.query("ROLLBACK")
    throw error
  } finally {
    client.release()
  }
}

export async function checkDatabaseConnection(): Promise<void> {
  await queryDatabase("SELECT 1")
}
