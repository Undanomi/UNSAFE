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
import {
  generateMachineGuidanceAction,
  retryMachineBuildAction,
  verifyMachineFlagAction,
} from "@/app/actions/machines"
import { MarkdownContent } from "@/components/markdown-content"
import type {
  FlagDefinition,
  MachineBuildState,
  MachineDetail,
  MachineGuidance,
} from "@/types/machine-detail"

type MachineDetailProps = {
  machine: MachineDetail
}

type FlagPanelProps = {
  flag: FlagDefinition
  onCorrect: () => void
}

function FlagPanel({ flag, onCorrect }: FlagPanelProps) {
  const [answer, setAnswer] = useState("")
  const [result, setResult] = useState<"correct" | "incorrect" | null>(
    flag.acquired ? "correct" : null,
  )
  const [isChecking, setIsChecking] = useState(false)

  async function handleSubmit() {
    if (!answer.trim() || isChecking) return
    setIsChecking(true)
    setResult(null)
    try {
      const verification = await verifyMachineFlagAction(flag.machineId, flag.kind, answer)
      if (verification.success) {
        setResult(verification.correct ? "correct" : "incorrect")
        if (verification.correct) onCorrect()
      }
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <section className="rounded-3xl border border-[#e5e5e2] bg-white p-6 shadow-sm max-sm:p-5">
      <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
        {flag.label}
      </h2>
      <div className="mt-5 flex gap-3 max-sm:flex-col">
        <input
          autoComplete="off"
          className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
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
          className="inline-flex min-h-[46px] shrink-0 items-center justify-center rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold shadow-sm transition hover:-translate-y-px"
          disabled={!answer.trim() || isChecking}
          onClick={() => void handleSubmit()}
          type="button"
        >
          {isChecking ? "判定中…" : "判定する"}
        </button>
      </div>
      <div aria-live="polite">
        {result === "correct" ? (
          <p className="mt-3 text-[0.86rem] font-bold text-[#28633a]">正解です。</p>
        ) : null}
        {result === "incorrect" ? (
          <p className="mt-3 text-[0.86rem] font-bold text-[#9a392d]">一致しません。</p>
        ) : null}
      </div>
    </section>
  )
}

function GuidancePanel({
  guidance,
  locked,
  showIntroduction,
  target,
}: {
  guidance: MachineGuidance
  locked?: boolean
  showIntroduction: boolean
  target: "user" | "system"
}) {
  const [visibleHints, setVisibleHints] = useState<Set<number>>(() => new Set())
  const [confirmedCount, setConfirmedCount] = useState(0)
  const items = guidance.items.filter((item) => item.target_flag === target)
  if (items.length === 0) return null
  const visibleItems = items.slice(0, Math.min(confirmedCount + 1, items.length))

  return (
    <section className="rounded-3xl border border-[#ded5a9] bg-[#fffdf4] p-6 shadow-sm max-sm:p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#f2e9b7] text-[#655715]">
          <Lightbulb aria-hidden="true" size={18} strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
            {target === "user" ? "ユーザーフラグまでの誘導" : "システムフラグまでの誘導"}
          </h2>
          {showIntroduction ? (
            <MarkdownContent
              className="mt-2 leading-[1.7] text-[#61605b]"
              content={guidance.introduction}
            />
          ) : null}
        </div>
      </div>

      {locked ? (
        <p className="mt-5 rounded-2xl border border-[#e4ddbd] bg-white p-5 text-[0.9rem] font-bold text-[#61605b]">
          ユーザーフラグを取得すると、この誘導を確認できます。
        </p>
      ) : (
        <ol className="mt-5 grid gap-4">
          {visibleItems.map((item, index) => {
            const showHint = visibleHints.has(index)
            const confirmed = index < confirmedCount
            return (
              <li
                className="rounded-2xl border border-[#e4ddbd] bg-white p-5"
                key={`${target}-${item.title}-${item.question}`}
              >
                <p className="text-[0.78rem] font-extrabold text-[#766825]">
                  {index + 1} / {items.length}
                </p>
                <MarkdownContent
                  className="mt-2 text-[1.05rem] font-extrabold"
                  content={item.title}
                />
                <MarkdownContent
                  className="mt-3 leading-[1.7] text-[#343431]"
                  content={item.question}
                />
                {showHint ? (
                  <div className="mt-4 rounded-xl bg-[#f8f6eb] p-4">
                    <p className="text-[0.78rem] font-extrabold text-[#766825]">ヒント</p>
                    <MarkdownContent
                      className="mt-1 leading-[1.65] text-[#61605b]"
                      content={item.hint}
                    />
                  </div>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#d6d6d2] bg-white px-4 text-[0.86rem] font-extrabold"
                    onClick={() =>
                      setVisibleHints((current) => {
                        const next = new Set(current)
                        if (next.has(index)) next.delete(index)
                        else next.add(index)
                        return next
                      })
                    }
                    type="button"
                  >
                    {showHint ? "ヒントを閉じる" : "ヒントを表示"}
                  </button>
                  {confirmed ? (
                    <span className="inline-flex min-h-11 items-center gap-2 px-2 text-[0.86rem] font-extrabold text-[#28633a]">
                      <CheckCircle2 aria-hidden="true" size={17} />
                      確認済み
                    </span>
                  ) : (
                    <button
                      className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#20201e] px-4 text-[0.86rem] font-extrabold text-white"
                      onClick={() =>
                        setConfirmedCount((count) => Math.min(count + 1, items.length))
                      }
                      type="button"
                    >
                      {index + 1 < items.length ? "確認して次へ" : "確認する"}
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

export function MachineDetailView({ machine }: MachineDetailProps) {
  const [buildState, setBuildState] = useState<MachineBuildState>({
    status: machine.status ?? "ready",
    progress: machine.buildProgress ?? 0,
    failure: machine.buildFailure ?? null,
  })
  const [description, setDescription] = useState(machine.description)
  const [isRetrying, setIsRetrying] = useState(false)
  const [retryError, setRetryError] = useState("")
  const [guidance, setGuidance] = useState(machine.guidance)
  const [isGuidanceGenerating, setIsGuidanceGenerating] = useState(false)
  const [guidanceError, setGuidanceError] = useState("")
  const [userFlagAcquired, setUserFlagAcquired] = useState(machine.userFlag?.acquired ?? false)
  const [systemFlagAcquired, setSystemFlagAcquired] = useState(
    machine.systemFlag?.acquired ?? false,
  )
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

  async function handleGuidance() {
    if (isGuidanceGenerating || buildState.status !== "ready") return
    setIsGuidanceGenerating(true)
    setGuidanceError("")
    try {
      const result = await generateMachineGuidanceAction(machine.id, guidance !== null)
      if (!result.success) {
        setGuidanceError(result.message)
        return
      }
      setGuidance(result.guidance)
    } catch {
      setGuidanceError("誘導問題を作成できませんでした。もう一度お試しください。")
    } finally {
      setIsGuidanceGenerating(false)
    }
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
          {canDownload ? (
            <a
              className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] max-sm:flex-1"
              href={`/api/machines/${encodeURIComponent(machine.id)}/download`}
            >
              <Download aria-hidden="true" size={18} strokeWidth={2} />
              ダウンロード
            </a>
          ) : (
            <button
              className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm max-sm:flex-1"
              disabled
              type="button"
            >
              <Download aria-hidden="true" size={18} strokeWidth={2} />
              {isBuilding ? "ビルド中" : "利用できません"}
            </button>
          )}
          <button
            className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold text-[#20201e] shadow-sm transition hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-55 max-sm:flex-1"
            disabled={isGuidanceGenerating || buildState.status !== "ready"}
            onClick={() => void handleGuidance()}
            type="button"
          >
            {isGuidanceGenerating ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
            ) : (
              <Lightbulb aria-hidden="true" size={18} strokeWidth={2} />
            )}
            {isGuidanceGenerating ? "作成中…" : guidance ? "誘導問題を再生成する" : "誘導問題"}
          </button>
        </div>
      </header>

      {guidanceError ? (
        <p className="rounded-2xl border border-[#e3bdb7] bg-[#fff8f6] p-4 text-[0.86rem] font-bold text-[#9a392d]">
          {guidanceError}
        </p>
      ) : null}

      {machine.status !== undefined ? (
        <BuildStatusPanel
          canRetry={machine.canRetry === true}
          error={retryError}
          isRetrying={isRetrying}
          onRetry={handleRetryBuild}
          state={buildState}
        />
      ) : null}

      <section className="rounded-3xl border border-[#e5e5e2] bg-white p-6 shadow-sm max-sm:p-5">
        <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
          マシンの説明
        </h2>
        <p className="mt-3 leading-[1.75] text-[#61605b]">{description}</p>
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

      {showFlags && (machine.userFlag || machine.systemFlag) ? (
        <div className="grid gap-5">
          {machine.userFlag ? (
            <>
              {guidance ? (
                <GuidancePanel
                  guidance={guidance}
                  key={`user-${JSON.stringify(guidance)}`}
                  showIntroduction
                  target="user"
                />
              ) : null}
              <FlagPanel flag={machine.userFlag} onCorrect={() => setUserFlagAcquired(true)} />
            </>
          ) : null}
          {machine.systemFlag ? (
            <>
              {guidance ? (
                <GuidancePanel
                  guidance={guidance}
                  key={`system-${JSON.stringify(guidance)}`}
                  locked={machine.userFlag !== null && !userFlagAcquired}
                  showIntroduction={!guidance.items.some((item) => item.target_flag === "user")}
                  target="system"
                />
              ) : null}
              <FlagPanel
                flag={{ ...machine.systemFlag, acquired: systemFlagAcquired }}
                onCorrect={() => setSystemFlagAcquired(true)}
              />
            </>
          ) : null}
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
      <section className="flex items-center gap-3 rounded-2xl border border-[#bed8c5] bg-[#f4fbf6] p-5 text-[#28633a]">
        <CheckCircle2 aria-hidden="true" size={20} />
        <p className="text-[0.9rem] font-extrabold">マシンのビルドが完了しました。</p>
      </section>
    )
  }

  if (state.status === "failed") {
    const safetyRefused = state.failure?.kind === "ai_safety_refusal"
    const retryAllowed = canRetry && state.failure?.retryAllowed !== false
    return (
      <section className="rounded-2xl border border-[#e3bdb7] bg-[#fff8f6] p-5">
        <div className="flex items-start gap-3 text-[#9a392d]">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
          <div>
            <h2 className="font-extrabold">
              {safetyRefused
                ? "安全上の理由でAIが処理を拒否しました"
                : "マシンのビルドに失敗しました"}
            </h2>
            {state.failure ? (
              <p className="mt-2 text-[0.84rem] font-bold leading-relaxed">
                {state.failure.summary}
              </p>
            ) : null}
            {safetyRefused ? (
              <p className="mt-2 text-[0.8rem] leading-relaxed">
                このマシンの処理は停止しました。同じマシンをそのまま再ビルドすることはできません。
              </p>
            ) : null}
          </div>
        </div>
        {retryAllowed ? (
          <button
            className="mt-4 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#20201e] px-4 text-[0.86rem] font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-55"
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
        {error ? <p className="mt-3 text-[0.84rem] font-bold text-[#9a392d]">{error}</p> : null}
      </section>
    )
  }

  if (state.status === "cancelled") {
    return (
      <section className="rounded-2xl border border-[#d6d6d2] bg-[#f8f8f7] p-5">
        <div className="flex items-start gap-3 text-[#61605b]">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
          <h2 className="font-extrabold">マシン作成は中止されました</h2>
        </div>
        {canRetry ? (
          <button
            className="mt-4 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#20201e] px-4 text-[0.86rem] font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isRetrying}
            onClick={onRetry}
            type="button"
          >
            {isRetrying ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : (
              <RefreshCw aria-hidden="true" size={17} />
            )}
            {isRetrying ? "再開中…" : "もう一度作成する"}
          </button>
        ) : null}
        {error ? <p className="mt-3 text-[0.84rem] font-bold text-[#9a392d]">{error}</p> : null}
      </section>
    )
  }

  return (
    <section className="rounded-2xl border border-[#d6d6d2] bg-[#f8f8f7] p-5">
      <div className="flex items-center justify-between gap-4">
        <span className="flex items-center gap-2 text-[0.9rem] font-extrabold">
          <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
          {message}
        </span>
        <span className="text-[0.8rem] font-bold text-[#61605b]">{state.progress}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#dfdfdb]">
        <span
          className="block h-full rounded-full bg-[#20201e] transition-[width]"
          style={{ width: `${state.progress}%` }}
        />
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
