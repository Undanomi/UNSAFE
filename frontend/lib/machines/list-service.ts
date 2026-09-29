import "server-only"

import { queryDatabase } from "@/lib/database/client"
import {
  MACHINE_PAGE_SIZE,
  type MachineListItem,
  type MachineListQuery,
  type MachineListResult,
} from "@/lib/machines/list-query"
import type { MachineRecord } from "@/types/postgres"

type MachineListRow = Pick<
  MachineRecord,
  "created_at" | "description" | "id" | "level" | "name" | "published" | "status" | "tags"
> & {
  author_id: string
  author: string
  author_icon_url: string
  is_owned: boolean
  is_solved: boolean
}

const solvedCondition = `m.created_by <> $1 AND EXISTS (
  SELECT 1 FROM machine_solutions s
  WHERE s.user_id = $1 AND s.machine_id = m.id
)`

function escapeLike(value: string) {
  return value.replace(/[\\%_]/g, "\\$&")
}

function buildFilters(viewerUserId: string, query: MachineListQuery) {
  const values: unknown[] = [viewerUserId]
  const conditions = [
    "m.status = 'ready'",
    query.owned ? "m.created_by = $1" : "(m.published = true OR m.created_by = $1)",
  ]

  if (query.level.length) {
    values.push(query.level)
    conditions.push(`m.level = ANY($${values.length}::text[])`)
  }
  if (query.tag) {
    values.push(query.tag)
    conditions.push(`$${values.length}::text = ANY(m.tags)`)
  }
  if (query.q) {
    values.push(`%${escapeLike(query.q)}%`)
    conditions.push(`(
      m.name ILIKE $${values.length} ESCAPE '\\'
      OR EXISTS (
        SELECT 1 FROM unnest(m.tags) AS tag
        WHERE tag ILIKE $${values.length} ESCAPE '\\'
      )
    )`)
  }
  if (query.solved) {
    conditions.push(`${query.solved === "no" ? "NOT " : ""}(${solvedCondition})`)
  }
  return { values, where: conditions.join(" AND ") }
}

export async function getMachineListService(
  viewerUserId: string,
  query: MachineListQuery,
): Promise<MachineListResult> {
  const filters = buildFilters(viewerUserId, query)
  const countResult = await queryDatabase<{ total: string }>(
    `SELECT count(*)::text AS total FROM machines m WHERE ${filters.where}`,
    filters.values,
  )
  const total = Number(countResult.rows[0]?.total ?? 0)
  const pageCount = Math.max(1, Math.ceil(total / MACHINE_PAGE_SIZE))
  const page = Math.min(query.page, pageCount)
  const values = [...filters.values, MACHINE_PAGE_SIZE, (page - 1) * MACHINE_PAGE_SIZE]
  const limitParameter = values.length - 1
  const offsetParameter = values.length
  const direction = query.sort === "asc" ? "ASC" : "DESC"

  const result = await queryDatabase<MachineListRow>(
    `SELECT
       m.id, m.name, m.description, m.tags, m.level, m.created_at,
       m.published, m.status, m.created_by AS author_id, u.name AS author,
       u.icon_url AS author_icon_url,
       (m.created_by = $1) AS is_owned,
       (${solvedCondition}) AS is_solved
     FROM machines m
     JOIN users u ON u.id = m.created_by
     WHERE ${filters.where}
     ORDER BY m.created_at ${direction}, m.id ASC
     LIMIT $${limitParameter} OFFSET $${offsetParameter}`,
    values,
  )
  const machines: MachineListItem[] = result.rows.map((row) => ({
    id: row.id,
    name: row.name,
    description: row.description,
    tags: row.tags,
    level: row.level,
    created_at: row.created_at.toISOString(),
    published: row.published,
    status: row.status,
    authorId: row.author_id,
    author: row.author || "ユーザー",
    authorAvatarUrl: row.author_icon_url,
    isOwned: row.is_owned,
    isSolved: row.is_solved,
  }))
  return { machines, total, page, pageCount }
}
