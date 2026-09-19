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
  "grid size-11 shrink-0 place-items-center rounded-lg border border-[#d6d6d2] text-sm font-bold transition-colors sm:size-12 sm:text-base"

const difficultyLabels = { easy: "Easy", medium: "Medium", hard: "High" }
const fieldClass =
  "block h-11 w-full rounded-xl border border-[#d6d6d2] bg-white px-3 pr-12 text-sm font-normal outline-none transition-[border-color,box-shadow] placeholder:text-[#969691] focus:border-[#20201e] focus:ring-2 focus:ring-[#20201e]/10"
const linkClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#d6d6d2] px-4 text-sm font-bold hover:bg-[#f8f8f7]"

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
    <section className="grid gap-7">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#f8f8f7]">
            <LayoutDashboard aria-hidden="true" size={22} />
          </span>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">マシン一覧</h1>
            <p className="mt-2 text-sm leading-relaxed text-[#61605b]">
              公開済みの学習環境から、次の挑戦を見つけましょう。
            </p>
          </div>
        </div>
        <Link
          className={`${linkClass} bg-[#20201e] text-white hover:bg-[#393934]`}
          href="/machines/chat"
        >
          <CirclePlus aria-hidden="true" size={18} />
          マシン作成
        </Link>
      </div>

      <Form
        action="/machines"
        key={`filters:${machineListHref(query)}`}
        className="grid gap-4 rounded-2xl border border-[#e5e5e2] bg-[#fafaf9] p-4 sm:p-5"
        aria-label="マシンの検索条件"
      >
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
          <label className="flex min-w-0 flex-col gap-2 text-sm leading-5 font-bold">
            難易度
            <span className="relative block">
              <select
                className={`${fieldClass} appearance-none`}
                name="level"
                defaultValue={query.level}
              >
                <option value="">すべて</option>
                <option value="easy">{difficultyLabels.easy}</option>
                <option value="medium">{difficultyLabels.medium}</option>
                <option value="hard">{difficultyLabels.hard}</option>
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
              className="size-4 accent-[#20201e]"
              type="checkbox"
              name="owned"
              value="1"
              defaultChecked={query.owned}
            />
            自分が作成したマシンのみ
          </label>
          <div className="flex items-center gap-3">
            <Link className="p-2 text-sm underline underline-offset-4" href="/machines">
              条件をリセット
            </Link>
            <button
              className="min-h-11 rounded-xl bg-[#20201e] px-6 text-sm font-bold text-white transition-colors hover:bg-[#393934]"
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
        <h2 className="text-lg font-bold">
          利用できるマシン{" "}
          <span className="ml-2 text-sm font-normal text-[#61605b]">{total} 件</span>
        </h2>
        {total > 0 && (
          <p className="text-sm text-[#61605b]">
            {(page - 1) * MACHINE_PAGE_SIZE + 1}–{Math.min(page * MACHINE_PAGE_SIZE, total)}{" "}
            件を表示
          </p>
        )}
      </div>
      {machines.length ? (
        <div className="overflow-x-auto rounded-2xl border border-[#e5e5e2] bg-white">
          <table className="w-full min-w-[860px] table-fixed text-left text-sm">
            <caption className="sr-only">利用できるマシン一覧</caption>
            <thead className="border-b border-[#d6d6d2] bg-[#f8f8f7] text-xs text-[#61605b]">
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
            <tbody className="divide-y divide-[#e5e5e2]">
              {machines.map((machine) => (
                <tr key={machine.id} className="align-top transition-colors hover:bg-[#fafaf9]">
                  <th scope="row" className="px-5 py-5 font-normal">
                    <Link
                      className="inline-flex max-w-full items-start gap-2 font-bold hover:underline"
                      href={`/machines/${encodeURIComponent(machine.id)}`}
                      prefetch={false}
                    >
                      <span className="break-words [overflow-wrap:anywhere]">{machine.name}</span>
                      <ArrowUpRight className="mt-0.5 shrink-0" aria-hidden="true" size={16} />
                    </Link>
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[#61605b] [overflow-wrap:anywhere]">
                      {machine.description || machine.summary || "概要はまだ登録されていません。"}
                    </p>
                  </th>
                  <td className="px-3 py-5">
                    {machine.tags.length === 0 && <span className="text-xs text-[#61605b]">—</span>}
                    <ul className="flex flex-wrap gap-1.5" aria-label="タグ">
                      {[...new Set(machine.tags)].map((tag) => (
                        <li
                          className="max-w-full rounded-md bg-[#f1f1ee] px-2 py-1 text-xs text-[#61605b] [overflow-wrap:anywhere]"
                          key={tag}
                        >
                          {tag}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-3 py-5">
                    <span className="inline-flex rounded-full bg-[#f1f1ee] px-2.5 py-1 text-xs font-bold">
                      {difficultyLabels[machine.level]}
                    </span>
                  </td>
                  <td className="px-3 py-5">
                    <span
                      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${machine.isSolved ? "bg-emerald-50 text-emerald-800" : "bg-[#f8f8f7] text-[#61605b]"}`}
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
                        className="grid size-7 shrink-0 place-items-center rounded-full bg-[#20201e] text-xs text-white"
                      >
                        {machine.author.slice(0, 1)}
                      </span>
                      <span className="pt-1 text-xs [overflow-wrap:anywhere]">
                        {machine.author}
                      </span>
                    </Link>
                  </td>
                  <td className="px-3 py-6 text-xs text-[#61605b]">
                    {createdDate(machine.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-2xl bg-[#f8f8f7] px-6 py-12 text-center text-sm text-[#61605b]">
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
              className={`${paginationClass} bg-white text-[#61605b] hover:border-[#20201e] hover:text-[#20201e]`}
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
              className={`${paginationClass} cursor-not-allowed bg-white text-[#61605b] opacity-40`}
            >
              <ChevronLeft aria-hidden="true" size={22} strokeWidth={2.5} />
            </button>
          )}
          {machinePaginationPages(page, pageCount).map((item) =>
            typeof item === "string" ? (
              <span
                key={item}
                className="grid h-11 w-5 shrink-0 place-items-center text-lg font-bold text-[#a3a3a3]"
                aria-hidden="true"
              >
                …
              </span>
            ) : item === page ? (
              <span
                key={item}
                aria-current="page"
                className={`${paginationClass} border-[#20201e] bg-[#20201e] text-white`}
              >
                {item}
              </span>
            ) : (
              <Link
                key={item}
                prefetch={false}
                href={machineListHref(query, item)}
                aria-label={`${item} ページ目`}
                className={`${paginationClass} bg-white text-[#61605b] hover:border-[#20201e] hover:text-[#20201e]`}
              >
                {item}
              </Link>
            ),
          )}
          {page < pageCount ? (
            <Link
              prefetch={false}
              aria-label="次のページ"
              className={`${paginationClass} bg-white text-[#61605b] hover:border-[#20201e] hover:text-[#20201e]`}
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
              className={`${paginationClass} cursor-not-allowed bg-white text-[#61605b] opacity-40`}
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
      className="rounded-2xl bg-[#f8f8f7] px-6 py-12 text-center text-sm text-[#61605b]"
    >
      読み込んでいます
    </p>
  )
}
