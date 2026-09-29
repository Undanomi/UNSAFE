import {
  ArrowUpRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  List,
  SearchX,
  X,
} from "lucide-react"
import Form from "next/form"
import Image from "next/image"
import Link from "next/link"
import type { ReactNode } from "react"
import { MachineFilterResetButton } from "@/app/(private)/machines/machine-filter-reset-button"
import { MACHINE_DIFFICULTY_LABELS, MACHINE_LEVELS } from "@/lib/machines/difficulty"
import {
  MACHINE_PAGE_SIZE,
  MAX_MACHINE_TAGS,
  type MachineListQuery,
  type MachineListResult,
  machineListHref,
} from "@/lib/machines/list-query"

const paginationClass =
  "slsg-pagination-button grid size-11 shrink-0 place-items-center rounded-md border text-sm font-bold sm:size-12 sm:text-base"

const difficultyClasses = {
  very_easy: "slsg-difficulty-very-easy",
  easy: "slsg-difficulty-easy",
  medium: "slsg-difficulty-medium",
  hard: "slsg-difficulty-high",
}
const fieldClass =
  "slsg-machine-filter-field block h-11 w-full rounded-lg border px-3 pr-12 text-sm font-normal outline-none"

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
    <section className="slsg-machine-list relative z-[2] mx-auto grid max-w-[1600px] gap-5">
      <header className="slsg-machine-list-hero relative pt-3">
        <p className="slsg-page-eyebrow">MACHINE DIRECTORY</p>
        <h1 className="slsg-machine-page-title slsg-heading-offset-up mt-[13px] font-bold">
          マシン一覧
        </h1>
        <p className="slsg-machine-page-description slsg-heading-offset-up slsg-muted mt-4 max-w-[44rem]">
          作成したマシンと、公開済みの学習環境を確認できます。
        </p>
      </header>

      <section
        aria-label="マシン一覧の操作"
        className="slsg-machine-actions grid max-w-[640px] grid-cols-[1.08fr_1fr] gap-4 max-md:grid-cols-1"
      >
        <Link
          className="slsg-machine-create-button group min-h-[85px] justify-start px-7"
          href="/machines/chat"
        >
          <CirclePlus aria-hidden="true" size={28} strokeWidth={1.7} />
          <span className="text-left">
            <span className="block text-[1.03rem] font-bold">新しいマシンを作成</span>
            <span className="slsg-machine-create-caption mt-0.5 block text-[0.8rem] font-normal">
              対話形式で設定を入力します
            </span>
          </span>
        </Link>
        <a
          className="slsg-machine-create-button group min-h-[85px] justify-start px-7"
          href="#available-machines"
        >
          <List aria-hidden="true" size={28} strokeWidth={1.7} />
          <span className="text-left text-[1.03rem] font-bold">公開済みマシンを確認</span>
        </a>
      </section>

      <Form
        action="/machines"
        key={`filters:${machineListHref(query)}`}
        className="slsg-machine-filter-panel grid gap-4 rounded-[14px] border p-4 sm:p-5"
        aria-label="マシンの検索条件"
      >
        {query.tags.map((tag) => (
          <input key={tag} name="tag" type="hidden" value={tag} />
        ))}
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
        {query.tags.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#a8b5cc]">
            <span>タグで絞り込み中:</span>
            {query.tags.map((tag) => (
              <span
                className="inline-flex max-w-full items-center gap-1 rounded-md border border-[#78bfd5] bg-[#23445c] py-1 pr-1 pl-2 text-[#d8f6ff]"
                key={tag}
              >
                <span className="min-w-0 [overflow-wrap:anywhere]">{tag}</span>
                <Link
                  aria-label={`タグ「${tag}」の絞り込みを解除`}
                  className="grid size-6 shrink-0 place-items-center rounded hover:bg-[#3a6478] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#9cecfc]"
                  href={machineListHref(
                    { ...query, tags: query.tags.filter((selected) => selected !== tag) },
                    1,
                  )}
                  prefetch={false}
                >
                  <X aria-hidden="true" size={14} />
                </Link>
              </span>
            ))}
          </div>
        ) : null}
        <div className="grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr]">
          <fieldset className="min-w-0 sm:col-span-2 xl:col-span-1">
            <legend className="mb-2 p-0 text-sm leading-5 font-bold">難易度</legend>
            <div className="slsg-machine-filter-options flex min-h-11 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-3">
              {MACHINE_LEVELS.map((level) => (
                <label
                  key={level}
                  className="flex min-h-[42px] shrink-0 items-center gap-2 text-sm leading-5"
                >
                  <input
                    className="size-4 accent-[#78bfd5]"
                    type="checkbox"
                    name="level"
                    value={level}
                    defaultChecked={query.level.includes(level)}
                  />
                  {MACHINE_DIFFICULTY_LABELS[level]}
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
              className="size-4 accent-[#78bfd5]"
              type="checkbox"
              name="owned"
              value="1"
              defaultChecked={query.owned}
            />
            自分が作成したマシンのみ
          </label>
          <div className="flex items-center gap-3">
            <MachineFilterResetButton />
            <button
              className="slsg-machine-filter-submit min-h-11 rounded-lg border px-6 text-sm font-bold"
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
  const firstVisible = total > 0 ? (page - 1) * MACHINE_PAGE_SIZE + 1 : 0
  const lastVisible = Math.min(page * MACHINE_PAGE_SIZE, total)

  return (
    <section
      aria-label="検索結果"
      className="slsg-panel slsg-machine-table-panel rounded-[14px]"
      id="available-machines"
    >
      <div aria-hidden="true" className="slsg-machine-table-glow">
        <span className="slsg-machine-table-glow-top" />
        <span className="slsg-machine-table-glow-bottom" />
        <span className="slsg-machine-table-glow-left" />
        <span className="slsg-machine-table-glow-right" />
      </div>
      <div className="slsg-machine-table-surface">
        <div className="slsg-machine-table-titlebar flex min-h-[77px] items-center justify-between gap-4 border-b px-9 max-sm:px-5">
          <h2 className="text-[clamp(1.25rem,1.6vw,1.5rem)] font-bold tracking-[-0.02em]">
            利用できるマシン
            <span className="ml-3 text-[0.8rem] font-normal text-[#a8b5cc]">{total}件</span>
          </h2>
          {total > 0 ? (
            <p className="text-[0.78rem] text-[#a4b0cc]">
              {firstVisible}–{lastVisible}件を表示
            </p>
          ) : null}
        </div>
        {machines.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] table-fixed text-left text-[0.9rem]">
              <caption className="sr-only">利用できるマシン一覧</caption>
              <thead className="slsg-machine-table-columns border-b text-[0.78rem] font-medium tracking-[0.02em] text-[#b8c3d6]">
                <tr>
                  <th scope="col" className="w-[30%] px-9 py-5">
                    マシン名
                  </th>
                  <th scope="col" className="w-[17%] px-4 py-5">
                    タグ
                  </th>
                  <th scope="col" className="w-[13%] px-4 py-5">
                    難易度
                  </th>
                  <th scope="col" className="w-[12%] px-4 py-5">
                    回答状態
                  </th>
                  <th scope="col" className="w-[15%] px-4 py-5">
                    作成者
                  </th>
                  <th scope="col" className="w-[13%] px-4 py-5">
                    作成日
                  </th>
                </tr>
              </thead>
              <tbody>
                {machines.map((machine) => (
                  <tr
                    key={machine.id}
                    className="slsg-machine-row border-b align-middle last:border-b-0"
                  >
                    <th scope="row" className="px-9 py-5 font-normal">
                      <Link
                        className="slsg-machine-name inline-flex max-w-full items-start gap-2 text-[1.03rem] font-bold"
                        href={`/machines/${encodeURIComponent(machine.id)}`}
                        prefetch={false}
                      >
                        <span className="break-words [overflow-wrap:anywhere]">{machine.name}</span>
                        <ArrowUpRight className="mt-0.5 shrink-0" aria-hidden="true" size={16} />
                      </Link>
                      <p className="mt-2 line-clamp-2 text-[0.76rem] leading-relaxed text-[#a7b3c9] [overflow-wrap:anywhere]">
                        {machine.description || "説明はまだ登録されていません。"}
                      </p>
                    </th>
                    <td className="px-4 py-5">
                      {machine.tags.length === 0 ? (
                        <span className="text-xs text-[#8292aa]">—</span>
                      ) : null}
                      <ul className="flex flex-wrap gap-1.5" aria-label="タグ">
                        {[...new Set(machine.tags)].map((tag) => {
                          const selected = query.tags.includes(tag)
                          const tagClass = `inline-block max-w-full rounded-md border px-2 py-1 text-xs [overflow-wrap:anywhere] ${selected ? "border-[#78bfd5] bg-[#23445c] text-[#d8f6ff]" : "border-[#3a4c69] bg-[#18243a] text-[#a8b5cc]"}`
                          return (
                            <li className="max-w-full" key={tag}>
                              {selected || query.tags.length >= MAX_MACHINE_TAGS ? (
                                <span className={tagClass}>{tag}</span>
                              ) : (
                                <Link
                                  aria-label={`タグ「${tag}」で絞り込む`}
                                  className={`${tagClass} hover:border-[#78bfd5] hover:text-[#d8f6ff] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#9cecfc]`}
                                  href={machineListHref(
                                    { ...query, tags: [...query.tags, tag] },
                                    1,
                                  )}
                                  prefetch={false}
                                >
                                  {tag}
                                </Link>
                              )}
                            </li>
                          )
                        })}
                      </ul>
                    </td>
                    <td className="px-4 py-5">
                      <span
                        className={`slsg-difficulty inline-flex rounded-full px-3 py-1.5 text-xs font-bold ${difficultyClasses[machine.level]}`}
                      >
                        {MACHINE_DIFFICULTY_LABELS[machine.level]}
                      </span>
                    </td>
                    <td className="px-4 py-5">
                      <span
                        className={`inline-flex whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-bold ${machine.isSolved ? "slsg-status-public" : "slsg-status-private"}`}
                      >
                        {machine.isSolved ? "回答済み" : "未回答"}
                      </span>
                    </td>
                    <td className="px-4 py-5">
                      <Link
                        className="slsg-machine-author flex items-center gap-3 font-medium"
                        href={`/users/${encodeURIComponent(machine.authorId)}`}
                        prefetch={false}
                      >
                        <span
                          aria-hidden="true"
                          className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full border border-[#52627e] bg-[#2a3956] text-xs text-white"
                        >
                          {machine.authorAvatarUrl ? (
                            <Image
                              alt=""
                              className="object-cover"
                              fill
                              referrerPolicy="no-referrer"
                              sizes="40px"
                              src={machine.authorAvatarUrl}
                              unoptimized
                            />
                          ) : (
                            machine.author.slice(0, 1)
                          )}
                        </span>
                        <span className="slsg-machine-author-name text-xs [overflow-wrap:anywhere]">
                          {machine.author}
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-6 text-xs text-[#a8b5cc]">
                      {createdDate(machine.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="slsg-machine-empty">
            <SearchX aria-hidden="true" size={30} strokeWidth={1.6} />
            <p>条件に一致するマシンがありません。</p>
            <span>検索条件を変更して、もう一度お試しください。</span>
          </div>
        )}
        <div className="slsg-machine-table-footer grid min-h-[87px] items-center gap-4 border-t px-9 max-sm:px-5">
          <span className="text-[0.8rem] text-[#a4b0cc]">
            全{total}件中 {firstVisible}–{lastVisible}件を表示
          </span>
          {total > 0 ? (
            <nav
              aria-label="ページ切り替え"
              className="flex max-w-full flex-wrap items-center justify-center gap-2"
            >
              {page > 1 ? (
                <Link
                  prefetch={false}
                  aria-label="前のページ"
                  className={`${paginationClass} text-[#d9e4f5]`}
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
                  className={`${paginationClass} cursor-not-allowed text-[#8292aa] opacity-40`}
                >
                  <ChevronLeft aria-hidden="true" size={22} strokeWidth={2.5} />
                </button>
              )}
              {machinePaginationPages(page, pageCount).map((item) =>
                typeof item === "string" ? (
                  <span
                    key={item}
                    className="grid h-11 w-5 shrink-0 place-items-center text-lg font-bold text-[#8292aa]"
                    aria-hidden="true"
                  >
                    …
                  </span>
                ) : item === page ? (
                  <span
                    key={item}
                    aria-current="page"
                    className={`${paginationClass} is-current text-white`}
                  >
                    {item}
                  </span>
                ) : (
                  <Link
                    key={item}
                    prefetch={false}
                    href={machineListHref(query, item)}
                    aria-label={`${item} ページ目`}
                    className={`${paginationClass} text-[#d9e4f5]`}
                  >
                    {item}
                  </Link>
                ),
              )}
              {page < pageCount ? (
                <Link
                  prefetch={false}
                  aria-label="次のページ"
                  className={`${paginationClass} text-[#d9e4f5]`}
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
                  className={`${paginationClass} cursor-not-allowed text-[#8292aa] opacity-40`}
                >
                  <ChevronRight aria-hidden="true" size={22} strokeWidth={2.5} />
                </button>
              )}
            </nav>
          ) : null}
        </div>
      </div>
    </section>
  )
}

export function MachineListLoading() {
  return (
    <p
      role="status"
      className="slsg-panel rounded-[14px] px-6 py-14 text-center text-sm text-[#a8b5cc]"
    >
      読み込んでいます
    </p>
  )
}
