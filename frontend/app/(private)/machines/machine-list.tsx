import {
  ArrowUpRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  LayoutDashboard,
} from "lucide-react"
import Form from "next/form"
import Link from "next/link"
import type { ReactNode } from "react"
import {
  MACHINE_PAGE_SIZE,
  type MachineListQuery,
  type MachineListResult,
  machineListHref,
} from "@/lib/machines/list-query"

const paginationClass =
  "grid size-11 shrink-0 place-items-center rounded-lg border border-[var(--line)] text-sm font-bold transition-colors sm:size-12 sm:text-base"

const difficultyLabels = { easy: "Easy", medium: "Medium", hard: "High" }
const fieldClass =
  "field-control block h-11 w-full rounded-lg px-3 pr-12 text-sm font-normal placeholder:text-[var(--ink-faint)]"
const linkClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold"

function createdDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? "作成日不明"
    : new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeZone: "Asia/Tokyo" }).format(date)
}

function machinePaginationPages(page: number, pageCount: number): (number | string)[] {
  const visible = [...new Set([1, page - 1, page, page + 1, pageCount])]
    .filter((value) => value >= 1 && value <= pageCount)
    .sort((a, b) => a - b)
  const pages: (number | string)[] = []
  for (const [index, value] of visible.entries()) {
    const previous = visible[index - 1]
    if (previous !== undefined && value - previous === 2) pages.push(previous + 1)
    else if (previous !== undefined && value - previous > 2) pages.push(`ellipsis-${previous}`)
    pages.push(value)
  }
  return pages
}

export function MachineList({ query, children }: { query: MachineListQuery; children: ReactNode }) {
  return (
    <section className="grid gap-8">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="mono-label mb-4 flex items-center gap-2 text-[var(--ink-soft)]">
            <span className="size-1.5 bg-[var(--accent)]" />
            Machine index
          </p>
          <div className="flex items-start gap-3">
            <span className="mt-1 grid size-9 place-items-center rounded-lg border border-[var(--line)] bg-[var(--surface)] text-[var(--signal)]">
              <LayoutDashboard aria-hidden="true" size={18} strokeWidth={1.8} />
            </span>
            <div>
              <h1 className="display-heading text-[clamp(2rem,3.6vw,3.35rem)] leading-[1.05]">
                マシン一覧
              </h1>
              <p className="mt-3 leading-[1.75] text-[var(--ink-soft)]">
                公開済みの学習環境から、次の挑戦を見つけましょう。
              </p>
            </div>
          </div>
        </div>
        <Link className={`${linkClass} primary-action`} href="/machines/chat">
          <CirclePlus aria-hidden="true" size={18} />
          マシン作成
        </Link>
      </div>

      <Form
        action="/machines"
        key={`filters:${machineListHref(query)}`}
        className="surface-panel grid gap-4 rounded-2xl p-4 sm:p-5"
        aria-label="マシンの検索条件"
      >
        <div className="flex items-center gap-2 border-b border-[var(--line)] pb-3">
          <span className="size-1.5 bg-[var(--signal)]" />
          <span className="mono-label text-[var(--ink-soft)]">Search protocol</span>
        </div>
        <label className="flex min-w-0 flex-col gap-2 text-sm leading-5 font-bold">
          キーワード
          <input
            className={fieldClass}
            type="search"
            name="q"
            defaultValue={query.q}
            maxLength={100}
            placeholder="マシン名・タグで検索"
          />
        </label>
        <div className="grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr]">
          <fieldset className="min-w-0 sm:col-span-2 xl:col-span-1">
            <legend className="mb-2 p-0 text-sm leading-5 font-bold">難易度</legend>
            <div className="flex min-h-11 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-3">
              {(["easy", "medium", "hard"] as const).map((level) => (
                <label
                  key={level}
                  className="flex min-h-[42px] shrink-0 items-center gap-2 text-sm leading-5"
                >
                  <input
                    className="size-4 accent-[var(--signal)]"
                    type="checkbox"
                    name="level"
                    value={level}
                    defaultChecked={query.level.includes(level)}
                  />
                  {difficultyLabels[level]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex min-w-0 flex-col gap-2 text-sm leading-5 font-bold">
            回答状態
            <span className="relative block">
              <select
                className={`${fieldClass} appearance-none`}
                name="solved"
                defaultValue={query.solved}
              >
                <option value="">すべて</option>
                <option value="yes">回答済み</option>
                <option value="no">未回答</option>
              </select>
              <ChevronDown
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2"
                size={18}
                strokeWidth={1.8}
              />
            </span>
          </label>
          <label className="flex min-w-0 flex-col gap-2 text-sm leading-5 font-bold">
            作成日
            <span className="relative block">
              <select
                className={`${fieldClass} appearance-none`}
                name="sort"
                defaultValue={query.sort}
              >
                <option value="desc">新しい順</option>
                <option value="asc">古い順</option>
              </select>
              <ChevronDown
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2"
                size={18}
                strokeWidth={1.8}
              />
            </span>
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4 pt-0">
          <label className="flex min-h-11 shrink-0 items-center gap-2 text-sm leading-5">
            <input
              className="size-4 accent-[var(--signal)]"
              type="checkbox"
              name="owned"
              value="1"
              defaultChecked={query.owned}
            />
            自分が作成したマシンのみ
          </label>
          <div className="flex items-center gap-3">
            <Link
              className="p-2 text-sm text-[var(--ink-soft)] underline underline-offset-4 hover:text-[var(--ink)]"
              href="/machines"
            >
              条件をリセット
            </Link>
            <button
              className="primary-action min-h-11 rounded-lg px-6 text-sm font-bold"
              type="submit"
            >
              検索する
            </button>
          </div>
        </div>
      </Form>

      {children}
    </section>
  )
}

export function MachineListResults({
  result,
  query,
}: {
  result: MachineListResult
  query: MachineListQuery
}) {
  const { machines, total, page, pageCount } = result
  return (
    <section aria-label="検索結果" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="mono-label mb-1.5 text-[var(--signal)]">Available nodes</p>
          <h2 className="text-lg font-bold">
            利用できるマシン{" "}
            <span className="ml-2 text-sm font-normal text-[var(--ink-soft)]">{total} 件</span>
          </h2>
        </div>
        {total > 0 && (
          <p className="font-mono text-xs text-[var(--ink-soft)]">
            {(page - 1) * MACHINE_PAGE_SIZE + 1}–{Math.min(page * MACHINE_PAGE_SIZE, total)}{" "}
            件を表示
          </p>
        )}
      </div>
      {machines.length ? (
        <div className="surface-panel overflow-x-auto rounded-2xl">
          <table className="w-full min-w-[860px] table-fixed text-left text-sm">
            <caption className="sr-only">利用できるマシン一覧</caption>
            <thead className="border-b border-[var(--line)] bg-[var(--surface-muted)] text-xs text-[var(--ink-soft)]">
              <tr>
                <th scope="col" className="w-[30%] px-5 py-4">
                  マシン名
                </th>
                <th scope="col" className="w-[22%] px-3 py-4">
                  タグ
                </th>
                <th scope="col" className="w-[10%] px-3 py-4">
                  難易度
                </th>
                <th scope="col" className="w-[12%] px-3 py-4">
                  回答状態
                </th>
                <th scope="col" className="w-[14%] px-3 py-4">
                  作成者
                </th>
                <th scope="col" className="w-[12%] px-3 py-4">
                  作成日
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {machines.map((machine) => (
                <tr
                  key={machine.id}
                  className="align-top transition-colors hover:bg-[var(--signal-soft)]/30"
                >
                  <th scope="row" className="px-5 py-5 font-normal">
                    <Link
                      className="inline-flex max-w-full items-start gap-2 font-bold hover:underline"
                      href={`/machines/${encodeURIComponent(machine.id)}`}
                      prefetch={false}
                    >
                      <span className="break-words [overflow-wrap:anywhere]">{machine.name}</span>
                      <ArrowUpRight className="mt-0.5 shrink-0" aria-hidden="true" size={16} />
                    </Link>
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[var(--ink-soft)] [overflow-wrap:anywhere]">
                      {machine.description || machine.summary || "概要はまだ登録されていません。"}
                    </p>
                  </th>
                  <td className="px-3 py-5">
                    {machine.tags.length === 0 && (
                      <span className="text-xs text-[var(--ink-soft)]">—</span>
                    )}
                    <ul className="flex flex-wrap gap-1.5" aria-label="タグ">
                      {[...new Set(machine.tags)].map((tag) => (
                        <li
                          className="max-w-full rounded-md border border-[var(--line)] bg-[var(--surface-muted)] px-2 py-1 text-xs text-[var(--ink-soft)] [overflow-wrap:anywhere]"
                          key={tag}
                        >
                          {tag}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-3 py-5">
                    <span className="inline-flex rounded-md bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-bold">
                      {difficultyLabels[machine.level]}
                    </span>
                  </td>
                  <td className="px-3 py-5">
                    <span
                      className={`inline-flex whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-bold ${machine.isSolved ? "bg-[var(--success-soft)] text-[var(--success)]" : "bg-[var(--surface-muted)] text-[var(--ink-soft)]"}`}
                    >
                      {machine.isSolved ? "回答済み" : "未回答"}
                    </span>
                  </td>
                  <td className="px-3 py-5">
                    <Link
                      className="flex items-start gap-2 font-bold hover:underline"
                      href={`/users/${encodeURIComponent(machine.authorId)}`}
                      prefetch={false}
                    >
                      <span
                        aria-hidden="true"
                        className="grid size-7 shrink-0 place-items-center rounded-full border border-[var(--line-strong)] bg-[var(--surface-muted)] text-xs text-[var(--ink)]"
                      >
                        {machine.author.slice(0, 1)}
                      </span>
                      <span className="pt-1 text-xs [overflow-wrap:anywhere]">
                        {machine.author}
                      </span>
                    </Link>
                  </td>
                  <td className="px-3 py-6 font-mono text-xs text-[var(--ink-soft)]">
                    {createdDate(machine.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--surface-muted)] px-6 py-12 text-center text-sm text-[var(--ink-soft)]">
          マシンがありません。
        </p>
      )}
      {total > 0 && (
        <nav
          aria-label="ページ切り替え"
          className="mt-4 flex flex-wrap items-center justify-center gap-2 sm:gap-3"
        >
          {page > 1 ? (
            <Link
              prefetch={false}
              aria-label="前のページ"
              className={`${paginationClass} bg-[var(--surface)] text-[var(--ink-soft)] hover:border-[var(--signal)] hover:text-[var(--signal)]`}
              href={machineListHref(query, page - 1)}
              rel="prev"
            >
              <ChevronLeft aria-hidden="true" size={22} strokeWidth={2.5} />
            </Link>
          ) : (
            <button
              type="button"
              disabled
              aria-label="前のページ"
              className={`${paginationClass} cursor-not-allowed bg-[var(--surface)] text-[var(--ink-soft)] opacity-40`}
            >
              <ChevronLeft aria-hidden="true" size={22} strokeWidth={2.5} />
            </button>
          )}
          {machinePaginationPages(page, pageCount).map((item) =>
            typeof item === "string" ? (
              <span
                key={item}
                className="grid h-11 w-5 shrink-0 place-items-center text-lg font-bold text-[var(--ink-faint)]"
                aria-hidden="true"
              >
                …
              </span>
            ) : item === page ? (
              <span
                key={item}
                aria-current="page"
                className={`${paginationClass} border-[var(--signal-solid)] bg-[var(--signal-solid)] text-[var(--inverse-ink)]`}
              >
                {item}
              </span>
            ) : (
              <Link
                key={item}
                prefetch={false}
                href={machineListHref(query, item)}
                aria-label={`${item} ページ目`}
                className={`${paginationClass} bg-[var(--surface)] text-[var(--ink-soft)] hover:border-[var(--signal)] hover:text-[var(--signal)]`}
              >
                {item}
              </Link>
            ),
          )}
          {page < pageCount ? (
            <Link
              prefetch={false}
              aria-label="次のページ"
              className={`${paginationClass} bg-[var(--surface)] text-[var(--ink-soft)] hover:border-[var(--signal)] hover:text-[var(--signal)]`}
              href={machineListHref(query, page + 1)}
              rel="next"
            >
              <ChevronRight aria-hidden="true" size={22} strokeWidth={2.5} />
            </Link>
          ) : (
            <button
              type="button"
              disabled
              aria-label="次のページ"
              className={`${paginationClass} cursor-not-allowed bg-[var(--surface)] text-[var(--ink-soft)] opacity-40`}
            >
              <ChevronRight aria-hidden="true" size={22} strokeWidth={2.5} />
            </button>
          )}
        </nav>
      )}
    </section>
  )
}

export function MachineListLoading() {
  return (
    <p
      role="status"
      className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--surface-muted)] px-6 py-12 text-center text-sm text-[var(--ink-soft)]"
    >
      読み込んでいます
    </p>
  )
}
