"use client"

import {
  AlertCircle,
  ArrowLeft,
  BookOpenText,
  CheckCircle2,
  ChevronDown,
  Download,
  Lightbulb,
  LoaderCircle,
  Pencil,
  RefreshCw,
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import {
  generateMachineGuidanceAction,
  retryMachineBuildAction,
  updateMachineDetailsAction,
  verifyMachineFlagAction,
} from "@/app/actions/machines"
import {
  type ActiveLimitNotice,
  ActiveSessionLimitPanel,
} from "@/components/active-session-limit-panel"
import { FlagCorrectEffect } from "@/components/flag-correct-effect"
import { MarkdownContent } from "@/components/markdown-content"
import { TerminalTelemetry } from "@/components/terminal-telemetry"
import type {
  FlagDefinition,
  MachineBuildState,
  MachineDetail,
  MachineGuidance,
} from "@/types/machine-detail"

type MachineDetailProps = {
  backHref?: string
  backLabel?: string
  machine: MachineDetail
}

type FlagPanelProps = {
  challengeName: string
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

function FlagPanel({ challengeName, flag, index, onCorrect }: FlagPanelProps) {
  const [answer, setAnswer] = useState("")
  const [result, setResult] = useState<"correct" | "incorrect" | null>(
    flag.acquired ? "correct" : null,
  )
  const [isChecking, setIsChecking] = useState(false)
  const [showCorrectEffect, setShowCorrectEffect] = useState(false)
  const [submittedFlag, setSubmittedFlag] = useState("")
  const submissionPendingRef = useRef(false)

  async function handleSubmit() {
    const normalizedAnswer = answer.trim()
    if (!normalizedAnswer || isChecking || result === "correct" || submissionPendingRef.current) {
      return
    }
    submissionPendingRef.current = true
    setIsChecking(true)
    setResult(null)
    try {
      const verification = await verifyMachineFlagAction(
        flag.machineId,
        flag.kind,
        normalizedAnswer,
      )
      if (verification.success) {
        setResult(verification.correct ? "correct" : "incorrect")
        if (verification.correct) {
          setSubmittedFlag(normalizedAnswer)
          setShowCorrectEffect(true)
          onCorrect()
        }
      }
    } finally {
      submissionPendingRef.current = false
      setIsChecking(false)
    }
  }

  return (
    <>
      <section className="slsg-detail-flag-row">
        <span aria-hidden="true" className="slsg-detail-flag-index">
          <svg className="slsg-detail-flag-index-border" viewBox="0 0 90 90">
            <title>フラグ番号の枠</title>
            <defs>
              <linearGradient
                id={`slsg-detail-flag-${index}-fill`}
                gradientUnits="userSpaceOnUse"
                x1="12"
                x2="78"
                y1="10"
                y2="82"
              >
                <stop offset="0" stopColor="#274975" stopOpacity="0.88" />
                <stop offset="1" stopColor="#142540" stopOpacity="0.94" />
              </linearGradient>
              <linearGradient
                id={`slsg-detail-flag-${index}-border`}
                gradientUnits="userSpaceOnUse"
                x1="0"
                x2="90"
                y1="0"
                y2="90"
              >
                <stop offset="0" stopColor="#c5f8ff" />
                <stop offset="0.3" stopColor="#78bfd5" />
                <stop offset="0.66" stopColor="#5698ff" />
                <stop offset="1" stopColor="#304e8e" stopOpacity="0.52" />
              </linearGradient>
              <linearGradient
                id={`slsg-detail-flag-${index}-glow-upper`}
                gradientUnits="userSpaceOnUse"
                x1="45"
                x2="7"
                y1="2"
                y2="37"
              >
                <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                <stop offset="0.34" stopColor="#78bfd5" stopOpacity="0.42" />
                <stop offset="0.68" stopColor="#c5f8ff" />
                <stop offset="0.84" stopColor="#78bfd5" stopOpacity="0.34" />
                <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
              </linearGradient>
              <linearGradient
                id={`slsg-detail-flag-${index}-glow-lower`}
                gradientUnits="userSpaceOnUse"
                x1="83"
                x2="49"
                y1="53"
                y2="87"
              >
                <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                <stop offset="0.16" stopColor="#78bfd5" stopOpacity="0.38" />
                <stop offset="0.32" stopColor="#c5f8ff" />
                <stop offset="0.62" stopColor="#78bfd5" stopOpacity="0.38" />
                <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              className="slsg-detail-flag-hex-base"
              d="M45 2q2 0 4 1l31 18q3 2 3 6v36q0 4-3 6L49 87q-4 2-8 0L10 69q-3-2-3-6V27q0-4 3-6L41 3q2-1 4-1Z"
              fill={`url(#slsg-detail-flag-${index}-fill)`}
              stroke={`url(#slsg-detail-flag-${index}-border)`}
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="slsg-detail-flag-hex-glow"
              d="M45 2 10 21q-3 2-3 6v10"
              stroke={`url(#slsg-detail-flag-${index}-glow-upper)`}
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="slsg-detail-flag-hex-glow"
              d="M83 53v10q0 4-3 6L49 87"
              stroke={`url(#slsg-detail-flag-${index}-glow-lower)`}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <span className="slsg-detail-flag-index-label">{String(index).padStart(2, "0")}</span>
        </span>
        <div className="slsg-detail-flag-content">
          <h3>{flag.label}</h3>
          <p>{flag.label}を発見したら、フラグを入力して判定してください。</p>
          <form
            className="slsg-detail-flag-entry"
            onSubmit={(event) => {
              event.preventDefault()
              void handleSubmit()
            }}
          >
            <input
              autoComplete="off"
              className="slsg-detail-flag-input"
              disabled={isChecking || result === "correct"}
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
              disabled={!answer.trim() || isChecking || result === "correct"}
              type="submit"
            >
              {isChecking ? "判定中…" : result === "correct" ? "正解済み" : "判定する"}
            </button>
          </form>
          <div aria-live="polite" className="slsg-detail-flag-result">
            {result === "correct" ? <p className="is-correct">正解です。</p> : null}
            {result === "incorrect" ? <p className="is-incorrect">一致しません。</p> : null}
          </div>
        </div>
      </section>
      <FlagCorrectEffect
        challengeName={challengeName}
        flagKind={flag.kind}
        level={index}
        onClose={() => setShowCorrectEffect(false)}
        open={showCorrectEffect}
        points={500}
        submittedFlag={submittedFlag}
      />
    </>
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
    <section className={`slsg-detail-guidance is-${target} ${locked ? "is-locked" : ""}`}>
      <header className="slsg-detail-guidance-header">
        <span aria-hidden="true" className="slsg-detail-guidance-icon">
          <Lightbulb size={21} strokeWidth={1.8} />
        </span>
        <div className="slsg-detail-guidance-heading">
          <p className="slsg-detail-guidance-eyebrow">
            {target === "user" ? "GUIDANCE / USER FLAG" : "GUIDANCE / SYSTEM FLAG"}
          </p>
          <h2>{target === "user" ? "ユーザーフラグまでの誘導" : "システムフラグまでの誘導"}</h2>
          {showIntroduction ? (
            <MarkdownContent
              className="slsg-detail-guidance-introduction slsg-detail-guidance-markdown"
              content={guidance.introduction}
            />
          ) : null}
        </div>
      </header>

      {locked ? (
        <div className="slsg-detail-guidance-locked">
          <span aria-hidden="true" />
          <p>ユーザーフラグを取得すると、この誘導を確認できます。</p>
        </div>
      ) : (
        <ol className="slsg-detail-guidance-list">
          {visibleItems.map((item, index) => {
            const showHint = visibleHints.has(index)
            const confirmed = index < confirmedCount
            return (
              <li
                className={`slsg-detail-guidance-item ${confirmed ? "is-confirmed" : ""}`}
                key={`${target}-${item.title}-${item.question}`}
              >
                <div aria-hidden="true" className="slsg-detail-guidance-progress">
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <i />
                  <small>{String(items.length).padStart(2, "0")}</small>
                </div>
                <MarkdownContent
                  className="slsg-detail-guidance-title slsg-detail-guidance-markdown"
                  content={item.title}
                />
                <MarkdownContent
                  className="slsg-detail-guidance-question slsg-detail-guidance-markdown"
                  content={item.question}
                />
                {showHint ? (
                  <aside className="slsg-detail-guidance-hint">
                    <p>HINT</p>
                    <MarkdownContent
                      className="slsg-detail-guidance-markdown"
                      content={item.hint}
                    />
                  </aside>
                ) : null}
                <div className="slsg-detail-guidance-actions">
                  <button
                    className="slsg-detail-guidance-button"
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
                    <span className="slsg-detail-guidance-confirmed">
                      <CheckCircle2 aria-hidden="true" size={17} />
                      確認済み
                    </span>
                  ) : (
                    <button
                      className="slsg-detail-guidance-button is-primary"
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

export function MachineDetailView({
  backHref = "/machines",
  backLabel = "マシン一覧へ戻る",
  machine,
}: MachineDetailProps) {
  const router = useRouter()
  const [savedFields, setSavedFields] = useState(() => ({
    name: machine.name,
    difficulty: machine.difficulty,
    visibility: machine.visibility,
  }))
  const [draftFields, setDraftFields] = useState(savedFields)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState("")
  const [buildState, setBuildState] = useState<MachineBuildState>({
    status: machine.status ?? "ready",
    progress: machine.buildProgress ?? 0,
    failure: machine.buildFailure ?? null,
  })
  const [description, setDescription] = useState(machine.description)
  const [isRetrying, setIsRetrying] = useState(false)
  const [retryError, setRetryError] = useState("")
  const [retryLimitNotice, setRetryLimitNotice] = useState<ActiveLimitNotice | null>(null)
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

  function startEditing() {
    setDraftFields(savedFields)
    setSaveError("")
    setIsEditing(true)
  }

  function cancelEditing() {
    setDraftFields(savedFields)
    setSaveError("")
    setIsEditing(false)
  }

  async function saveDetails() {
    if (isSaving) return
    setIsSaving(true)
    setSaveError("")
    const formData = new FormData()
    formData.set("name", draftFields.name)
    formData.set(
      "level",
      draftFields.difficulty === "High"
        ? "hard"
        : draftFields.difficulty === "Medium"
          ? "medium"
          : "easy",
    )
    formData.set("published", draftFields.visibility === "公開" ? "true" : "false")
    try {
      const result = await updateMachineDetailsAction(machine.id, formData)
      if (!result.success) {
        setSaveError(result.message)
        return
      }
      const nextFields = {
        name: result.machine.name,
        difficulty:
          result.machine.level === "hard"
            ? "High"
            : result.machine.level === "medium"
              ? "Medium"
              : "Easy",
        visibility: result.machine.published ? "公開" : "非公開",
      } as const
      setSavedFields(nextFields)
      setDraftFields(nextFields)
      setIsEditing(false)
      router.refresh()
    } catch {
      setSaveError("マシン情報を保存できませんでした。もう一度お試しください。")
    } finally {
      setIsSaving(false)
    }
  }

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
    setRetryLimitNotice(null)
    try {
      const result = await retryMachineBuildAction(machine.id)
      if (!result.success) {
        if ("code" in result && result.code === "active_session_limit") {
          setRetryLimitNotice({ message: result.message, activeChats: result.activeChats })
        } else {
          setRetryError(result.message)
        }
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

  const descriptionParagraphs = Array.from(description.matchAll(/[^。]+。?/g), (match) => ({
    text: match[0],
    start: match.index,
  }))
  if (descriptionParagraphs.length === 0) {
    descriptionParagraphs.push({ text: description, start: 0 })
  }

  return (
    <section className="slsg-machine-detail-page">
      <Link className="slsg-detail-back-link" href={backHref}>
        <ArrowLeft aria-hidden="true" size={19} strokeWidth={1.8} />
        {backLabel}
      </Link>
      <header className={`slsg-detail-hero${machine.canEdit ? " is-editable" : ""}`}>
        <div className="slsg-detail-heading">
          <h1>{savedFields.name}</h1>
          {machine.tags.length > 0 ? (
            <ul aria-label="タグ" className="slsg-detail-tags">
              {[...new Set(machine.tags)].map((tag) => (
                <li key={tag}>{tag}</li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="slsg-detail-actions">
          {machine.canEdit ? (
            <button
              aria-label="マシン情報を編集"
              className="slsg-detail-action"
              disabled={isEditing}
              onClick={startEditing}
              type="button"
            >
              <Pencil aria-hidden="true" size={22} strokeWidth={1.8} />
              編集
            </button>
          ) : null}
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

      {isEditing ? (
        <form
          className="slsg-detail-edit-form"
          onSubmit={(event) => {
            event.preventDefault()
            void saveDetails()
          }}
        >
          <h2>マシン情報を編集</h2>
          <div className="slsg-detail-edit-fields">
            <label>
              マシン名
              <input
                maxLength={40}
                onChange={(event) =>
                  setDraftFields((current) => ({ ...current, name: event.target.value }))
                }
                required
                type="text"
                value={draftFields.name}
              />
            </label>
            <label>
              難易度
              <span className="relative block">
                <select
                  className="slsg-machine-filter-field block h-11 w-full appearance-none rounded-lg border px-3 pr-12 text-sm font-normal outline-none"
                  onChange={(event) =>
                    setDraftFields((current) => ({
                      ...current,
                      difficulty: event.target.value as MachineDetail["difficulty"],
                    }))
                  }
                  value={draftFields.difficulty}
                >
                  <option value="Easy">Easy</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
                <ChevronDown
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2"
                  size={18}
                  strokeWidth={1.8}
                />
              </span>
            </label>
            <label>
              公開設定
              <span className="relative block">
                <select
                  className="slsg-machine-filter-field block h-11 w-full appearance-none rounded-lg border px-3 pr-12 text-sm font-normal outline-none"
                  onChange={(event) =>
                    setDraftFields((current) => ({
                      ...current,
                      visibility: event.target.value as MachineDetail["visibility"],
                    }))
                  }
                  value={draftFields.visibility}
                >
                  <option value="公開">公開</option>
                  <option value="非公開">非公開</option>
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
          {saveError ? (
            <p className="slsg-detail-edit-error" role="alert">
              {saveError}
            </p>
          ) : null}
          <div className="slsg-detail-edit-actions">
            <button disabled={isSaving} type="submit">
              {isSaving ? "保存中…" : "保存"}
            </button>
            <button disabled={isSaving} onClick={cancelEditing} type="button">
              取消
            </button>
          </div>
        </form>
      ) : null}

      {guidanceError ? (
        <div className="slsg-detail-notice is-error" role="alert">
          <AlertCircle aria-hidden="true" size={20} />
          <p>{guidanceError}</p>
        </div>
      ) : null}

      {machine.status !== undefined ? (
        <BuildStatusPanel
          activeLimitNotice={retryLimitNotice}
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
              <p key={paragraph.start}>{paragraph.text}</p>
            ))}
          </div>
        </section>

        <section className="slsg-detail-card slsg-detail-info-card">
          <h2 className="slsg-detail-card-heading">マシン情報</h2>
          <dl className="slsg-detail-info-list">
            {[
              ["公開状態", savedFields.visibility],
              ["難易度", savedFields.difficulty],
              ["作成者", machine.author],
              ["作成日", formatDisplayDate(machine.createdAt)],
            ].map(([label, value]) => (
              <div className="slsg-detail-info-row" key={label}>
                <dt>{label}</dt>
                <dd>
                  {label === "公開状態" ? (
                    <span
                      className={
                        savedFields.visibility === "公開"
                          ? "slsg-status-public"
                          : "slsg-status-private"
                      }
                    >
                      {value}
                      {savedFields.visibility === "非公開" ? " · 自分" : ""}
                    </span>
                  ) : null}
                  {label === "難易度" ? (
                    <span className={`slsg-difficulty ${DIFFICULTY_CLASS[savedFields.difficulty]}`}>
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
                  challengeName={savedFields.name}
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
                  challengeName={savedFields.name}
                  flag={{ ...machine.systemFlag, acquired: systemFlagAcquired }}
                  index={machine.userFlag ? 2 : 1}
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
  activeLimitNotice,
  canRetry,
  error,
  isRetrying,
  onRetry,
  state,
}: {
  activeLimitNotice: ActiveLimitNotice | null
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

  if (activeLimitNotice) {
    return (
      <section className="slsg-detail-build-status is-limit">
        <ActiveSessionLimitPanel notice={activeLimitNotice} />
        {canRetry ? (
          <button disabled={isRetrying} onClick={onRetry} type="button">
            {isRetrying ? "再ビルドを開始中…" : "もう一度ビルドする"}
          </button>
        ) : null}
      </section>
    )
  }

  if (state.status === "failed") {
    const safetyRefused = state.failure?.kind === "ai_safety_refusal"
    const retryAllowed = canRetry && state.failure?.retryAllowed !== false
    return (
      <section className="slsg-detail-build-status is-failed">
        <div className="slsg-detail-build-message">
          <AlertCircle aria-hidden="true" size={20} />
          <div className="slsg-detail-build-copy">
            <h2>
              {safetyRefused
                ? "安全上の理由でAIが処理を拒否しました"
                : "マシンのビルドに失敗しました"}
            </h2>
            {state.failure ? <p>{state.failure.summary}</p> : null}
            {safetyRefused ? (
              <p className="is-note">
                このマシンの処理は停止しました。同じマシンをそのまま再ビルドすることはできません。
              </p>
            ) : null}
          </div>
        </div>
        {retryAllowed ? (
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
      <section className="slsg-detail-build-status is-cancelled">
        <div className="slsg-detail-build-message">
          <AlertCircle aria-hidden="true" size={20} />
          <h2>マシン作成は中止されました</h2>
        </div>
        {canRetry ? (
          <button disabled={isRetrying} onClick={onRetry} type="button">
            {isRetrying ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            ) : (
              <RefreshCw aria-hidden="true" size={17} />
            )}
            {isRetrying ? "再開中…" : "もう一度作成する"}
          </button>
        ) : null}
        {error ? <p className="slsg-detail-build-error">{error}</p> : null}
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

export function MissingMachine({
  backHref = "/machines",
  backLabel = "マシン一覧へ戻る",
}: {
  backHref?: string
  backLabel?: string
}) {
  return (
    <section className="slsg-panel slsg-state-card">
      <div className="slsg-state-card-content">
        <span aria-hidden="true" className="slsg-state-card-icon">
          <AlertCircle size={25} strokeWidth={1.7} />
        </span>
        <h1>このマシンは見つかりませんでした。</h1>
        <p>一覧から別のマシンを選択してください。</p>
        <Link className="slsg-state-card-action" href={backHref}>
          <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
          {backLabel}
        </Link>
      </div>
    </section>
  )
}
