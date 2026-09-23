"use client"

import {
  AlertCircle,
  ArrowLeft,
  BookOpenText,
  CheckCircle2,
  Download,
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
import { TerminalTelemetry } from "@/components/terminal-telemetry"
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
  index: number
  onCorrect: () => void
}

const DIFFICULTY_CLASS: Record<MachineDetail["difficulty"], string> = {
  "Very Easy": "slsg-difficulty-very-easy",
  Easy: "slsg-difficulty-easy",
  Medium: "slsg-difficulty-medium",
  High: "slsg-difficulty-high",
}

function formatDisplayDate(date: string) {
  const parsedDate = new Date(date)
  if (!Number.isNaN(parsedDate.getTime())) {
    return new Intl.DateTimeFormat("ja-JP", {
      dateStyle: "medium",
      timeZone: "Asia/Tokyo",
    }).format(parsedDate)
  }
  return date
}

function FlagPanel({ flag, index, onCorrect }: FlagPanelProps) {
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
    <section className="slsg-detail-flag-row">
      <span aria-hidden="true" className="slsg-detail-flag-index">
        <svg className="slsg-detail-flag-index-border" viewBox="0 0 74 74">
          <title>フラグ番号の枠</title>
          <polygon points="37,1 69,19 69,55 37,73 5,55 5,19" />
        </svg>
        <span className="slsg-detail-flag-index-label">{String(index).padStart(2, "0")}</span>
      </span>
      <div className="slsg-detail-flag-content">
        <h3>{flag.label}</h3>
        <p>{flag.label}を発見したら、フラグを入力して判定してください。</p>
        <div className="slsg-detail-flag-entry">
          <input
            autoComplete="off"
            className="slsg-detail-flag-input"
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
            className="slsg-detail-action"
            disabled={!answer.trim() || isChecking}
            onClick={() => void handleSubmit()}
            type="button"
          >
            {isChecking ? "判定中…" : "判定する"}
          </button>
        </div>
        <div aria-live="polite" className="slsg-detail-flag-result">
          {result === "correct" ? <p className="is-correct">正解です。</p> : null}
          {result === "incorrect" ? <p className="is-incorrect">一致しません。</p> : null}
        </div>
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
    <section className="slsg-detail-guidance rounded-3xl border border-[#ded5a9] bg-[#fffdf4] p-6 shadow-sm max-sm:p-5">
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

  const descriptionParagraphs = description.match(/[^。]+。?/g) ?? [description]

  return (
    <section className="slsg-machine-detail-page">
      <Link className="slsg-detail-back-link" href="/machines">
        <ArrowLeft aria-hidden="true" size={19} strokeWidth={1.8} />
        マシン一覧へ戻る
      </Link>
      <header className="slsg-detail-hero">
        <div className="slsg-detail-heading">
          <h1>{machine.name}</h1>
          <p>{machine.summary}</p>
        </div>
        <div className="slsg-detail-actions">
          {canDownload ? (
            <a
              className="slsg-detail-action"
              href={`/api/machines/${encodeURIComponent(machine.id)}/download`}
            >
              <Download aria-hidden="true" size={22} strokeWidth={1.8} />
              ダウンロード
            </a>
          ) : (
            <button className="slsg-detail-action" disabled type="button">
              <Download aria-hidden="true" size={22} strokeWidth={1.8} />
              {isBuilding ? "ビルド中" : "利用できません"}
            </button>
          )}
          <button
            className="slsg-detail-action"
            disabled={isGuidanceGenerating || buildState.status !== "ready"}
            onClick={() => void handleGuidance()}
            type="button"
          >
            {isGuidanceGenerating ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={22} />
            ) : (
              <BookOpenText aria-hidden="true" size={22} strokeWidth={1.6} />
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

      <div className="slsg-detail-overview">
        <section className="slsg-detail-card slsg-detail-description-card">
          <h2 className="slsg-detail-card-heading">マシンの説明</h2>
          <div className="slsg-detail-description-body">
            {descriptionParagraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>

        <section className="slsg-detail-card slsg-detail-info-card">
          <h2 className="slsg-detail-card-heading">マシン情報</h2>
          <dl className="slsg-detail-info-list">
            {[
              ["公開状態", machine.visibility],
              ["難易度", machine.difficulty],
              ["テーマ", machine.theme],
              ["作成者", machine.author],
              ["作成日", formatDisplayDate(machine.createdAt)],
            ].map(([label, value]) => (
              <div className="slsg-detail-info-row" key={label}>
                <dt>{label}</dt>
                <dd>
                  {label === "公開状態" ? (
                    <span
                      className={
                        machine.visibility === "公開" ? "slsg-status-public" : "slsg-status-private"
                      }
                    >
                      {value}
                      {machine.visibility === "非公開" ? " · 自分" : ""}
                    </span>
                  ) : null}
                  {label === "難易度" ? (
                    <span className={`slsg-difficulty ${DIFFICULTY_CLASS[machine.difficulty]}`}>
                      {value}
                    </span>
                  ) : null}
                  {label !== "公開状態" && label !== "難易度" ? value : null}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      {showFlags && (machine.userFlag || machine.systemFlag) ? (
        <section className="slsg-detail-card slsg-detail-flags-card">
          <h2 className="slsg-detail-card-heading">フラグの提出</h2>
          <div className="slsg-detail-flags-body">
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
                <FlagPanel
                  flag={machine.userFlag}
                  index={1}
                  onCorrect={() => setUserFlagAcquired(true)}
                />
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
                  index={2}
                  onCorrect={() => setSystemFlagAcquired(true)}
                />
              </>
            ) : null}
          </div>
        </section>
      ) : null}
      <TerminalTelemetry />
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
      <section className="slsg-detail-build-status is-ready">
        <CheckCircle2 aria-hidden="true" size={20} />
        <p>マシンのビルドが完了しました。</p>
      </section>
    )
  }

  if (state.status === "failed") {
    return (
      <section className="slsg-detail-build-status is-failed">
        <div className="slsg-detail-build-message">
          <AlertCircle aria-hidden="true" size={20} />
          <h2>マシンのビルドに失敗しました</h2>
        </div>
        {canRetry ? (
          <button disabled={isRetrying} onClick={onRetry} type="button">
            {isRetrying ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : (
              <RefreshCw aria-hidden="true" size={17} />
            )}
            {isRetrying ? "再ビルドを開始中…" : "もう一度ビルドする"}
          </button>
        ) : null}
        {error ? <p className="slsg-detail-build-error">{error}</p> : null}
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
    <section className="slsg-detail-build-status is-building">
      <div className="slsg-detail-build-message">
        <span>
          <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
          {message}
        </span>
        <strong>{state.progress}%</strong>
      </div>
      <div className="slsg-detail-build-progress">
        <span style={{ width: `${state.progress}%` }} />
      </div>
    </section>
  )
}

export function MissingMachine() {
  return (
    <section className="slsg-panel grid gap-3 rounded-[14px] p-8">
      <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
        このマシンは見つかりませんでした。
      </h1>
      <p className="leading-[1.65] text-[#a9b5ca]">一覧から別のマシンを選択してください。</p>
      <Link
        className="inline-flex w-fit items-center gap-2 text-[0.86rem] font-bold text-[#dce8fa] underline underline-offset-4"
        href="/machines"
      >
        <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
        マシン一覧へ戻る
      </Link>
    </section>
  )
}
