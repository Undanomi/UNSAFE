"use client"

import { ArrowLeft, Download, HardDrive, Lightbulb } from "lucide-react"
import Link from "next/link"
import type { FlagDefinition, MachineDetail } from "@/stores/machine-detail"

type MachineDetailProps = {
  machine: MachineDetail
}

type FlagPanelProps = {
  flag: FlagDefinition
}

function FlagPanel({ flag }: FlagPanelProps) {
  return (
    <section className="rounded-3xl border border-[#e5e5e2] bg-white p-6 shadow-sm max-sm:p-5">
      <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
        {flag.label}
      </h2>
      <div className="mt-5 flex gap-3 max-sm:flex-col">
        <input
          className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
          placeholder="flag{...}"
        />
        <button
          className="inline-flex min-h-[46px] shrink-0 items-center justify-center rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold shadow-sm transition hover:-translate-y-px"
          type="button"
        >
          判定する
        </button>
      </div>
    </section>
  )
}

export function MachineDetailView({ machine }: MachineDetailProps) {
  function handleDownload() {
    return machine.id
  }

  return (
    <section className="grid gap-6">
      <Link
        className="inline-flex w-fit items-center gap-2 text-[0.86rem] font-bold text-[#61605b] transition hover:text-[#20201e]"
        href="/machines"
      >
        <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
        マシン一覧へ戻る
      </Link>
      <header className="flex items-start justify-between gap-6 max-md:flex-col">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-10 place-items-center rounded-xl border border-[#e5e5e2] bg-[#f8f8f7] text-[#20201e]">
            <HardDrive aria-hidden="true" size={20} strokeWidth={2} />
          </span>
          <div>
            <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
              {machine.name}
            </h1>
            <p className="mt-2 leading-[1.65] text-[#61605b]">{machine.summary}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 max-md:self-end max-sm:w-full max-sm:self-auto">
          <button
            className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] max-sm:flex-1"
            onClick={handleDownload}
            type="button"
          >
            <Download aria-hidden="true" size={18} strokeWidth={2} />
            ダウンロード
          </button>
          <button
            className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold text-[#20201e] shadow-sm transition hover:-translate-y-px max-sm:flex-1"
            type="button"
          >
            <Lightbulb aria-hidden="true" size={18} strokeWidth={2} />
            誘導問題
          </button>
        </div>
      </header>

      <section className="rounded-3xl border border-[#e5e5e2] bg-white p-6 shadow-sm max-sm:p-5">
        <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
          マシンの説明
        </h2>
        <p className="mt-3 leading-[1.75] text-[#61605b]">{machine.description}</p>
        <div className="mt-5 flex flex-wrap gap-2 text-[0.82rem] text-[#61605b]">
          <span className="rounded-full border border-[#d6d6d2] bg-white px-2.5 py-1 font-bold text-[#20201e]">
            {machine.visibility}
          </span>
          <span className="rounded-full border border-[#d6d6d2] bg-white px-2.5 py-1 font-bold">
            {machine.difficulty}
          </span>
          <span className="rounded-full border border-[#d6d6d2] bg-white px-2.5 py-1 font-bold">
            {machine.theme}
          </span>
          <span className="px-2.5 py-1">作成者 {machine.author}</span>
          <span className="px-2.5 py-1">作成日 {machine.createdAt}</span>
        </div>
      </section>

      <div className="grid gap-5">
        <FlagPanel flag={machine.userFlag} />
        <FlagPanel flag={machine.systemFlag} />
      </div>
    </section>
  )
}

export function MissingMachine() {
  return (
    <section className="grid gap-3 rounded-3xl border border-[#e5e5e2] bg-white p-8 shadow-sm">
      <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
        このマシンは見つかりませんでした。
      </h1>
      <p className="leading-[1.65] text-[#61605b]">一覧から別のマシンを選択してください。</p>
      <Link
        className="inline-flex w-fit items-center gap-2 text-[0.86rem] font-bold text-[#20201e] underline underline-offset-4"
        href="/machines"
      >
        <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
        マシン一覧へ戻る
      </Link>
    </section>
  )
}
