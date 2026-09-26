import type { MachineRecord } from "@/types/postgres"

export const MACHINE_PAGE_SIZE = 10
export type MachineListQuery = {
  page: number
  q: string
  level: MachineRecord["level"][]
  owned: boolean
  solved: "" | "yes" | "no"
  sort: "asc" | "desc"
}
export type MachineListItem = Pick<
  MachineRecord,
  "description" | "id" | "level" | "name" | "published" | "status" | "summary" | "tags"
> & {
  created_at: string
  authorId: string
  author: string
  authorAvatarUrl: string
  isOwned: boolean
  isSolved: boolean
}
export type MachineListResult = {
  machines: MachineListItem[]
  total: number
  page: number
  pageCount: number
}

export function parseMachineListQuery(
  params: Record<string, string | string[] | undefined>,
): MachineListQuery {
  const value = (key: string) => (typeof params[key] === "string" ? params[key] : "")
  const rawPage = value("page")
  const page = /^\d+$/.test(rawPage) ? Number(rawPage) : 1
  const rawLevels = Array.isArray(params.level) ? params.level : [params.level]
  const levels = (["easy", "medium", "hard"] as const).filter((level) => rawLevels.includes(level))
  const solved = value("solved")
  return {
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
    q: value("q").trim().slice(0, 100),
    level: levels,
    owned: value("owned") === "1",
    solved: solved === "yes" || solved === "no" ? solved : "",
    sort: value("sort") === "asc" ? "asc" : "desc",
  }
}

export function machineListHref(query: MachineListQuery, page = query.page) {
  const params = new URLSearchParams()
  if (query.q) params.set("q", query.q)
  for (const level of query.level) params.append("level", level)
  if (query.owned) params.set("owned", "1")
  if (query.solved) params.set("solved", query.solved)
  if (query.sort === "asc") params.set("sort", "asc")
  if (page > 1) params.set("page", String(page))
  return `/machines${params.size ? `?${params}` : ""}`
}

export function selectMachinePage(
  items: MachineListItem[],
  query: MachineListQuery,
): MachineListResult {
  const needle = query.q.toLocaleLowerCase("ja-JP")
  const matches = items.filter(
    (item) =>
      item.status === "ready" &&
      (item.published === true || item.isOwned) &&
      (!query.owned || item.isOwned) &&
      (query.level.length === 0 || query.level.includes(item.level)) &&
      (!query.solved || item.isSolved === (query.solved === "yes")) &&
      (!needle ||
        [item.name, ...item.tags].some((text) => text.toLocaleLowerCase("ja-JP").includes(needle))),
  )
  matches.sort((a, b) => {
    const dateOrder = (Date.parse(a.created_at) || 0) - (Date.parse(b.created_at) || 0)
    return (query.sort === "asc" ? dateOrder : -dateOrder) || a.id.localeCompare(b.id)
  })
  const pageCount = Math.max(1, Math.ceil(matches.length / MACHINE_PAGE_SIZE))
  const page = Math.min(query.page, pageCount)
  return {
    machines: matches.slice((page - 1) * MACHINE_PAGE_SIZE, page * MACHINE_PAGE_SIZE),
    total: matches.length,
    page,
    pageCount,
  }
}
