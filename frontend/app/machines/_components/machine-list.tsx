"use client"

import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  Globe2,
  LayoutDashboard,
} from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import type { MachineSummary } from "@/stores/machine-list"
import { userProfiles } from "@/stores/profile"

type MachineListProps = {
  machines: MachineSummary[]
}

const pageSize = 10

export function MachineList({ machines }: MachineListProps) {
  const [currentPage, setCurrentPage] = useState(0)
  const pages = Array.from({ length: Math.ceil(machines.length / pageSize) }, (_, pageIndex) =>
    machines.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize),
  )
  const hasMachines = pages.length > 0
  const visibleMachines = pages[currentPage] ?? []

  return (
    <section className="grid gap-7">
      <div className="flex items-start justify-between gap-6 max-sm:flex-col">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-10 place-items-center rounded-xl border border-[#e5e5e2] bg-[#f8f8f7] text-[#20201e]">
            <LayoutDashboard aria-hidden="true" size={20} strokeWidth={2} />
          </span>
          <div>
            <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
              マシン一覧
            </h1>
            <p className="mt-2 leading-[1.65] text-[#61605b]">
              作成したマシンと、公開済みの学習環境を確認できます。
            </p>
          </div>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
        <Link
          className="group flex items-center justify-between rounded-2xl border border-[#e5e5e2] bg-white p-5 transition hover:border-[#20201e] hover:shadow-sm"
          href="/machines/chat"
        >
          <span className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-[#20201e] text-white">
              <CirclePlus aria-hidden="true" size={19} strokeWidth={2} />
            </span>
            <span>
              <span className="block font-extrabold">新しいマシンを作成</span>
              <span className="mt-0.5 block text-[0.8rem] text-[#61605b]">
                対話形式で設定を入力します
              </span>
            </span>
          </span>
          <ArrowUpRight
            aria-hidden="true"
            className="text-[#61605b] group-hover:text-[#20201e]"
            size={18}
          />
        </Link>
        <a
          className="group flex items-center justify-between rounded-2xl border border-[#e5e5e2] bg-white p-5 transition hover:border-[#20201e] hover:shadow-sm"
          href="#available-machines"
        >
          <span className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl border border-[#d6d6d2] bg-[#f8f8f7]">
              <Globe2 aria-hidden="true" size={19} strokeWidth={2} />
            </span>
            <span>
              <span className="block font-extrabold">公開済みマシンを確認</span>
              <span className="mt-0.5 block text-[0.8rem] text-[#61605b]">
                学習したいテーマを一覧から選べます
              </span>
            </span>
          </span>
          <ArrowUpRight
            aria-hidden="true"
            className="text-[#61605b] group-hover:text-[#20201e]"
            size={18}
          />
        </a>
      </section>

      <section
        aria-label="マシン一覧"
        className="overflow-hidden rounded-3xl border border-[#e5e5e2] bg-white p-7 shadow-sm max-sm:p-4"
        id="available-machines"
      >
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
              利用できるマシン
            </h2>
          </div>
          {hasMachines ? (
            <span className="text-[0.8rem] text-[#61605b]">ページ {currentPage + 1}</span>
          ) : null}
        </div>
        {hasMachines ? (
          <>
            <div className="overflow-x-auto">
              <div className="grid min-w-[800px] grid-cols-[360px_180px_140px_120px] gap-4 border-b border-[#d6d6d2] px-4 py-3 text-[0.76rem] font-extrabold text-[#61605b]">
                <span>マシン名</span>
                <span>作成者</span>
                <span>作成日</span>
                <span>公開状態</span>
              </div>
              <ul aria-label="マシン詳細へのリンク一覧" className="min-w-[800px]">
                {visibleMachines.map((machine) => (
                  <li
                    className="grid grid-cols-[360px_180px_140px_120px] items-center gap-4 border-b border-[#d6d6d2] px-4 py-4 text-[0.88rem] last:border-b-0 hover:bg-white/45"
                    key={machine.id}
                  >
                    <span className="min-w-0">
                      <Link
                        className="grid min-w-0 gap-1 font-extrabold hover:underline"
                        href={`/machines/${machine.id}`}
                      >
                        <span className="truncate" title={machine.name}>
                          {machine.name}
                        </span>
                        <small className="text-[0.7rem] font-normal text-[#8a8984]">
                          ID: {machine.id}
                        </small>
                      </Link>
                    </span>
                    <Link
                      className="inline-flex items-center gap-2 font-bold hover:underline"
                      href={`/users/${machine.authorId}`}
                    >
                      <span
                        aria-hidden="true"
                        className="grid size-7 place-items-center rounded-full bg-[#20201e] text-[0.72rem] text-white"
                      >
                        {userProfiles[machine.authorId]?.initial ?? machine.author.slice(0, 1)}
                      </span>
                      {machine.author}
                    </Link>
                    <span>{machine.createdAt}</span>
                    <span>
                      <span className="inline-flex rounded-full border border-[#d6d6d2] bg-white px-2.5 py-1 text-[0.75rem] font-bold">
                        {machine.visibility}
                        {machine.isOwned ? " · 自分" : ""}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            {pages.length > 1 ? (
              <nav
                aria-label="ページ切り替え"
                className="mt-6 flex items-center justify-center gap-2"
              >
                <button
                  className="grid size-[38px] place-items-center rounded-xl border border-[#d6d6d2] bg-white text-[#20201e] shadow-sm disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={currentPage === 0}
                  onClick={() => setCurrentPage((page) => page - 1)}
                  type="button"
                >
                  <ChevronLeft aria-hidden="true" size={18} strokeWidth={2} />
                </button>
                {pages.map((page, index) => (
                  <button
                    aria-current={currentPage === index ? "page" : undefined}
                    className={`grid size-[38px] place-items-center rounded-xl border border-[#d6d6d2] text-sm font-extrabold ${
                      currentPage === index
                        ? "border-[#20201e] bg-[#20201e] text-white"
                        : "bg-white text-[#20201e] shadow-sm"
                    }`}
                    key={page[0]?.id ?? index}
                    onClick={() => setCurrentPage(index)}
                    type="button"
                  >
                    {index + 1}
                  </button>
                ))}
                <button
                  className="grid size-[38px] place-items-center rounded-xl border border-[#d6d6d2] bg-white text-[#20201e] shadow-sm disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={currentPage === pages.length - 1}
                  onClick={() => setCurrentPage((page) => page + 1)}
                  type="button"
                >
                  <ChevronRight aria-hidden="true" size={18} strokeWidth={2} />
                </button>
              </nav>
            ) : null}
          </>
        ) : (
          <div className="grid justify-items-center gap-4 rounded-2xl bg-[#f8f8f7] px-6 py-12 text-center">
            <p className="text-[0.9rem] text-[#61605b]">表示できるマシンはまだありません。</p>
            <Link
              className="inline-flex min-h-[42px] items-center justify-center rounded-xl bg-[#20201e] px-4 text-[0.86rem] font-extrabold text-white"
              href="/machines/chat"
            >
              マシンを作成
            </Link>
          </div>
        )}
      </section>
    </section>
  )
}
