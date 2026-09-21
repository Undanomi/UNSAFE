"use client"

import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  HardDrive,
  Lightbulb,
  LoaderCircle,
  RefreshCw,
} from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"
import { retryMachineBuildAction, verifyMachineFlagAction } from "@/app/actions/machines"
import type { FlagDefinition, MachineBuildState, MachineDetail } from "@/stores/machine-detail"

type MachineDetailProps = {
  machine: MachineDetail
}

type FlagPanelProps = {
  flag: FlagDefinition
}

function FlagPanel({ flag }: FlagPanelProps) {
  const [answer, setAnswer] = useState("")
  const [result, setResult] = useState<"correct" | "incorrect" | null>(null)
  const [isChecking, setIsChecking] = useState(false)

  async function handleSubmit() {
    if (!answer.trim() || isChecking) return
    setIsChecking(true)
    setResult(null)
    try {
      const verification = await verifyMachineFlagAction(flag.machineId, flag.kind, answer)
      if (verification.success) {
        setResult(verification.correct ? "correct" : "incorrect")
      }
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <section className="surface-panel rounded-2xl p-6 max-sm:p-5">
      <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
        {flag.label}
      </h2>
      <div className="mt-5 flex gap-3 max-sm:flex-col">
        <input
          autoComplete="off"
          className="field-control w-full rounded-lg px-[14px] py-[13px]"
          disabled={isChecking}
          maxLength={200}
          onChange={(event) => {
            setAnswer(event.target.value)
            setResult(null)
          }}
          placeholder="flag{...}"
          spellCheck={false}
          value={answer}
        />
        <button
          className="secondary-action inline-flex min-h-[46px] shrink-0 items-center justify-center rounded-lg px-[18px] text-[0.9rem] font-bold"
          disabled={!answer.trim() || isChecking}
          onClick={() => void handleSubmit()}
          type="button"
        >
          {isChecking ? "判定中…" : "判定する"}
        </button>
      </div>
      <div aria-live="polite">
        {result === "correct" ? (
          <p className="mt-3 text-[0.86rem] font-bold text-[var(--success)]">正解です。</p>
        ) : null}
        {result === "incorrect" ? (
          <p className="mt-3 text-[0.86rem] font-bold text-[var(--danger)]">一致しません。</p>
        ) : null}
      </div>
    </section>
  )
}

export function MachineDetailView({ machine }: MachineDetailProps) {
  const [buildState, setBuildState] = useState<MachineBuildState>({
    status: machine.status ?? "ready",
    progress: machine.buildProgress ?? 0,
  })
  const [description, setDescription] = useState(machine.description)
  const [isRetrying, setIsRetrying] = useState(false)
  const [retryError, setRetryError] = useState("")
  const isBuilding = buildState.status === "building" || buildState.status === "preparing"
  const canDownload = machine.status !== undefined && buildState.status === "ready"
  const showFlags = machine.status !== undefined && buildState.status === "ready"

  useEffect(() => {
    if (!isBuilding) return
    const abortController = new AbortController()
    let timeoutId: ReturnType<typeof setTimeout> | undefined

    async function poll() {
      try {
        const response = await fetch(`/api/machines/${encodeURIComponent(machine.id)}/status`, {
          cache: "no-store",
          signal: abortController.signal,
        })
        if (!response.ok) throw new Error("ビルド状態を取得できませんでした。")
        const state = (await response.json()) as MachineBuildState
        setBuildState(state)
        if (state.description) setDescription(state.description)
        if (state.status === "building" || state.status === "preparing") {
          timeoutId = setTimeout(poll, 5000)
        }
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          timeoutId = setTimeout(poll, 5000)
        }
      }
    }

    void poll()
    return () => {
      abortController.abort()
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [isBuilding, machine.id])

  async function handleRetryBuild() {
    setIsRetrying(true)
    setRetryError("")
    try {
      const result = await retryMachineBuildAction(machine.id)
      if (!result.success) {
        setRetryError(result.message)
        return
      }
      setBuildState(result.state)
      if (result.state.description) setDescription(result.state.description)
    } catch {
      setRetryError("再ビルドを開始できませんでした。もう一度お試しください。")
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <section className="grid gap-6">
      <Link
        className="inline-flex w-fit items-center gap-2 text-[0.86rem] font-bold text-[var(--ink-soft)] transition hover:text-[var(--signal)]"
        href="/machines"
      >
        <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
        マシン一覧へ戻る
      </Link>
      <header className="flex items-start justify-between gap-6 max-md:flex-col">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-10 place-items-center rounded-lg border border-[var(--line)] bg-[var(--surface)] text-[var(--signal)]">
            <HardDrive aria-hidden="true" size={20} strokeWidth={2} />
          </span>
          <div>
            <p className="mono-label mb-2 text-[var(--ink-soft)]">Machine node / {machine.id}</p>
            <h1 className="display-heading text-[clamp(1.75rem,3vw,2.75rem)] leading-[1.05]">
              {machine.name}
            </h1>
            <p className="mt-2 leading-[1.65] text-[var(--ink-soft)]">{machine.summary}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 max-md:self-end max-sm:w-full max-sm:self-auto">
          {canDownload ? (
            <a
              className="primary-action inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold max-sm:flex-1"
              href={`/api/machines/${encodeURIComponent(machine.id)}/download`}
            >
              <Download aria-hidden="true" size={18} strokeWidth={2} />
              ダウンロード
            </a>
          ) : (
            <button
              className="primary-action inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold max-sm:flex-1"
              disabled
              type="button"
            >
              <Download aria-hidden="true" size={18} strokeWidth={2} />
              {isBuilding ? "ビルド中" : "利用できません"}
            </button>
          )}
          <button
            className="secondary-action inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold max-sm:flex-1"
            type="button"
          >
            <Lightbulb aria-hidden="true" size={18} strokeWidth={2} />
            誘導問題
          </button>
        </div>
      </header>

      {machine.status !== undefined ? (
        <BuildStatusPanel
          canRetry={machine.canRetry === true}
          error={retryError}
          isRetrying={isRetrying}
          onRetry={handleRetryBuild}
          state={buildState}
        />
      ) : null}

      <section className="surface-panel rounded-2xl p-6 max-sm:p-5">
        <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
          マシンの説明
        </h2>
        <p className="mt-3 leading-[1.75] text-[var(--ink-soft)]">{description}</p>
        <div className="mt-5 flex flex-wrap gap-2 text-[0.82rem] text-[var(--ink-soft)]">
          <span className="rounded-md border border-[var(--signal)] bg-[var(--signal-soft)] px-2.5 py-1 font-bold text-[var(--ink)]">
            {machine.visibility}
          </span>
          <span className="rounded-md border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 font-bold">
            {machine.difficulty}
          </span>
          <span className="rounded-md border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 font-bold">
            {machine.theme}
          </span>
          <span className="px-2.5 py-1">作成者 {machine.author}</span>
          <span className="px-2.5 py-1">作成日 {machine.createdAt}</span>
        </div>
      </section>

      {showFlags && (machine.userFlag || machine.systemFlag) ? (
        <div className="grid gap-5">
          {machine.userFlag ? <FlagPanel flag={machine.userFlag} /> : null}
          {machine.systemFlag ? <FlagPanel flag={machine.systemFlag} /> : null}
        </div>
      ) : null}
    </section>
  )
}

function BuildStatusPanel({
  canRetry,
  error,
  isRetrying,
  onRetry,
  state,
}: {
  canRetry: boolean
  error: string
  isRetrying: boolean
  onRetry: () => void
  state: MachineBuildState
}) {
  const message =
    state.status === "preparing"
      ? "AIがビルド内容を生成しています"
      : state.progress >= 80 && state.progress < 90
        ? "ディスクイメージを変換しています"
        : "マシンをビルドしています"

  if (state.status === "ready") {
    return (
      <section className="flex items-center gap-3 rounded-xl border border-[var(--success)]/35 bg-[var(--success-soft)] p-5 text-[var(--success)]">
        <CheckCircle2 aria-hidden="true" size={20} />
        <p className="text-[0.9rem] font-extrabold">マシンのビルドが完了しました。</p>
      </section>
    )
  }

  if (state.status === "failed") {
    return (
      <section className="rounded-xl border border-[var(--danger)]/35 bg-[var(--danger-soft)] p-5">
        <div className="flex items-start gap-3 text-[var(--danger)]">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
          <div>
            <h2 className="font-extrabold">マシンのビルドに失敗しました</h2>
          </div>
        </div>
        {canRetry ? (
          <button
            className="primary-action mt-4 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-[0.86rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isRetrying}
            onClick={onRetry}
            type="button"
          >
            {isRetrying ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : (
              <RefreshCw aria-hidden="true" size={17} />
            )}
            {isRetrying ? "再ビルドを開始中…" : "もう一度ビルドする"}
          </button>
        ) : null}
        {error ? (
          <p className="mt-3 text-[0.84rem] font-bold text-[var(--danger)]">{error}</p>
        ) : null}
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-5">
      <div className="flex items-center justify-between gap-4">
        <span className="flex items-center gap-2 text-[0.9rem] font-extrabold">
          <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
          {message}
        </span>
        <span className="font-mono text-[0.8rem] font-bold text-[var(--ink-soft)]">
          {state.progress}%
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden bg-[var(--surface-strong)]">
        <span
          className="block h-full bg-[var(--signal)] transition-[width]"
          style={{ width: `${state.progress}%` }}
        />
      </div>
    </section>
  )
}

export function MissingMachine() {
  return (
    <section className="surface-panel grid gap-3 rounded-2xl p-8">
      <h1 className="display-heading text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05]">
        このマシンは見つかりませんでした。
      </h1>
      <p className="leading-[1.65] text-[var(--ink-soft)]">
        一覧から別のマシンを選択してください。
      </p>
      <Link
        className="inline-flex w-fit items-center gap-2 text-[0.86rem] font-bold text-[var(--signal)] underline underline-offset-4"
        href="/machines"
      >
        <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
        マシン一覧へ戻る
      </Link>
    </section>
  )
}
