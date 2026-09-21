"use client"

import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  LoaderCircle,
  Pencil,
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useCallback, useEffect, useRef, useState } from "react"
import {
  markMachineCreationFailedAction,
  prepareMachineCreationAction,
  saveChatProgressAction,
  startMachineBuildAction,
} from "@/app/actions/chat"
import {
  CHAT_CONFIG,
  CHAT_COPY,
  CHAT_PROMPTS,
  CHAT_STEPS,
  type ChatAnswers,
  type ChatSession,
  DIFFICULTY_OPTIONS,
  EMPTY_CHAT_ANSWERS,
  THEME_SUGGESTIONS,
  VISIBILITY_OPTIONS,
} from "@/stores/chat"

type ChatWorkspaceProps = {
  session: ChatSession
}

type ScenarioEvent = {
  event: string
  data: unknown
}

function readScenarioId(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("scenario" in data)) return null
  const scenario = data.scenario
  if (!scenario || typeof scenario !== "object" || !("scenario_id" in scenario)) return null
  return typeof scenario.scenario_id === "string" ? scenario.scenario_id : null
}

async function consumeScenarioStream(
  response: Response,
  onProgress: (generatedCharacters: number) => void,
): Promise<string> {
  if (!response.ok || !response.body) {
    throw new Error("AIサーバーに接続できませんでした。")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let generatedCharacters = 0

  function parseEvent(block: string): ScenarioEvent | null {
    let event = "message"
    const dataLines: string[] = []
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim()
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length === 0) return null
    try {
      return { event, data: JSON.parse(dataLines.join("\n")) }
    } catch {
      return null
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n")
    const blocks = buffer.split("\n\n")
    buffer = blocks.pop() ?? ""

    for (const block of blocks) {
      const parsed = parseEvent(block)
      if (!parsed) continue
      if (parsed.event === "scenario.delta") {
        const content =
          parsed.data && typeof parsed.data === "object" && "content" in parsed.data
            ? parsed.data.content
            : ""
        generatedCharacters += typeof content === "string" ? content.length : 0
        onProgress(generatedCharacters)
      }
      if (parsed.event === "scenario.error") throw new Error("シナリオ生成に失敗しました。")
      if (parsed.event === "scenario.completed") {
        const scenarioId = readScenarioId(parsed.data)
        if (!scenarioId) throw new Error("生成されたシナリオを確認できませんでした。")
        return scenarioId
      }
    }
    if (done) break
  }

  throw new Error("AIサーバーとの接続が途中で終了しました。")
}

function buildInitialAnswers(session: ChatSession): ChatAnswers {
  return { ...EMPTY_CHAT_ANSWERS, ...session.initialAnswers }
}

function isChatStepComplete(step: number, answers: ChatAnswers) {
  switch (step) {
    case CHAT_STEPS.machineName:
      return (
        answers.name.trim().length >= CHAT_CONFIG.machineNameMinLength &&
        answers.name.length <= CHAT_CONFIG.machineNameMaxLength
      )
    case CHAT_STEPS.visibility:
      return Boolean(answers.visibility)
    case CHAT_STEPS.theme:
      return answers.theme.trim().length > 0
    case CHAT_STEPS.difficulty:
      return Boolean(answers.difficulty)
    case CHAT_STEPS.userFlagChoice:
      return answers.needsUserFlag !== null
    case CHAT_STEPS.userFlagDetails:
      return answers.userFlagDetails.trim().length > 0
    case CHAT_STEPS.systemFlagChoice:
      return answers.needsSystemFlag !== null
    case CHAT_STEPS.systemFlagDetails:
      return answers.systemFlagDetails.trim().length > 0
    default:
      return false
  }
}

function getNextChatStep(step: number, answers: ChatAnswers) {
  if (step === CHAT_STEPS.userFlagChoice) {
    return answers.needsUserFlag ? CHAT_STEPS.userFlagDetails : CHAT_STEPS.systemFlagChoice
  }
  if (step === CHAT_STEPS.systemFlagChoice) {
    return answers.needsSystemFlag ? CHAT_STEPS.systemFlagDetails : CHAT_STEPS.complete
  }
  return step + CHAT_CONFIG.stepIncrement
}

function getChatValidationMessage(step: number) {
  return step === CHAT_STEPS.machineName
    ? CHAT_COPY.errors.machineName
    : CHAT_COPY.errors.answerRequired
}

function getChatPrompt(step: number, isBasicReady: boolean) {
  if (isBasicReady) return CHAT_COPY.basicReadyPrompt
  return CHAT_PROMPTS[step] ?? CHAT_COPY.completePrompt
}

function buildChatSummary(answers: ChatAnswers) {
  const { labels } = CHAT_COPY.summary
  return [
    [labels.machineName, answers.name],
    [labels.visibility, answers.visibility],
    [labels.theme, answers.theme],
    [labels.difficulty, answers.difficulty],
    [labels.userFlag, formatFlagSetting(answers.needsUserFlag)],
    [labels.systemFlag, formatFlagSetting(answers.needsSystemFlag)],
  ]
}

function buildChatTranscript(currentStep: number, isBasicReady: boolean, answers: ChatAnswers) {
  return Object.values(CHAT_STEPS)
    .filter((step) => step < CHAT_STEPS.complete)
    .filter((step) => step < currentStep || (isBasicReady && step === CHAT_STEPS.difficulty))
    .filter((step) => {
      if (step === CHAT_STEPS.userFlagDetails) return answers.needsUserFlag === true
      if (step === CHAT_STEPS.systemFlagDetails) return answers.needsSystemFlag === true
      return true
    })
    .map((step) => ({
      answer: getChatAnswer(step, answers),
      prompt: CHAT_PROMPTS[step],
      step,
    }))
}

function getChatAnswer(step: number, answers: ChatAnswers) {
  switch (step) {
    case CHAT_STEPS.machineName:
      return answers.name
    case CHAT_STEPS.visibility:
      return answers.visibility
    case CHAT_STEPS.theme:
      return answers.theme
    case CHAT_STEPS.difficulty:
      return answers.difficulty
    case CHAT_STEPS.userFlagChoice:
      return formatFlagSetting(answers.needsUserFlag)
    case CHAT_STEPS.userFlagDetails:
      return answers.userFlagDetails
    case CHAT_STEPS.systemFlagChoice:
      return formatFlagSetting(answers.needsSystemFlag)
    case CHAT_STEPS.systemFlagDetails:
      return answers.systemFlagDetails
    default:
      return ""
  }
}

function formatFlagSetting(value: boolean | null) {
  if (value === null) return ""
  return value ? CHAT_COPY.yesNo.yes : CHAT_COPY.yesNo.no
}

export function ChatWorkspace({ session }: ChatWorkspaceProps) {
  const router = useRouter()
  const [answers, setAnswers] = useState<ChatAnswers>(() => buildInitialAnswers(session))
  const [step, setStep] = useState(session.initialStep)
  const [basicReady, setBasicReady] = useState(() => session.status === "基本設定完了")
  const [sessionId, setSessionId] = useState<string | null>(() =>
    session.id === "session-new" ? null : session.id,
  )
  const [creationStatus, setCreationStatus] = useState(session.creationStatus)
  const [creationMessage, setCreationMessage] = useState("")
  const [error, setError] = useState("")
  const [editingStep, setEditingStep] = useState<number | null>(null)
  const [editingError, setEditingError] = useState("")
  const [isSummaryOpen, setIsSummaryOpen] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const conversationRef = useRef<HTMLDivElement>(null)
  const creationStartedRef = useRef(false)

  const progress = Math.min(step, CHAT_STEPS.systemFlagDetails)
  const isFinalStep = step === CHAT_STEPS.complete
  const prompt = getChatPrompt(step, basicReady)
  const transcript = buildChatTranscript(step, basicReady, answers)
  const chatProgress = `${step}:${basicReady}`

  useEffect(() => {
    if (!chatProgress) return
    const conversation = conversationRef.current
    if (conversation) {
      conversation.scrollTo({ behavior: "smooth", top: conversation.scrollHeight })
    }
  }, [chatProgress])

  function updateAnswers(values: Partial<ChatAnswers>) {
    setAnswers((current) => ({ ...current, ...values }))
    setError("")
    setEditingError("")
  }

  async function persistProgress(nextStep: number, nextBasicReady: boolean) {
    setIsSaving(true)
    const result = await saveChatProgressAction({
      sessionId,
      answers,
      currentStep: nextStep,
      basicReady: nextBasicReady,
    })
    setIsSaving(false)
    if (!result.success) {
      setError(result.message)
      return false
    }

    if (!sessionId) {
      setSessionId(result.sessionId)
      router.replace(`/machines/chat/${result.sessionId}`)
    }
    return true
  }

  async function advance() {
    if (!isChatStepComplete(step, answers)) {
      setError(getChatValidationMessage(step))
      return
    }
    if (step === CHAT_STEPS.difficulty) {
      if (!(await persistProgress(step, true))) return
      setBasicReady(true)
      return
    }
    const nextStep = getNextChatStep(step, answers)
    if (!(await persistProgress(nextStep, false))) return
    setStep(nextStep)
  }

  async function continueDetails() {
    if (!(await persistProgress(CHAT_STEPS.userFlagChoice, false))) return
    setBasicReady(false)
    setStep(CHAT_STEPS.userFlagChoice)
  }

  const runMachineCreation = useCallback(
    async (resume = false) => {
      if (!sessionId || creationStartedRef.current) return
      creationStartedRef.current = true
      setCreationStatus("generating_scenario")
      setCreationMessage("AIにマシン設定を送信しています…")
      setError("")

      try {
        if (!resume) {
          const preparation = await prepareMachineCreationAction(sessionId, answers)
          if (!preparation.success) throw new Error(preparation.message)
        }

        setCreationMessage("AIがシナリオを生成しています…")
        const response = await fetch(`/api/chat/${encodeURIComponent(sessionId)}/scenario`, {
          cache: "no-store",
        })
        const scenarioId = await consumeScenarioStream(response, (characters) => {
          setCreationMessage(`AIがシナリオを生成しています… ${characters.toLocaleString()}文字`)
        })

        setCreationMessage("シナリオが完成しました。ビルドを開始しています…")
        const build = await startMachineBuildAction(sessionId, scenarioId)
        if (!build.success || !build.machineId) {
          throw new Error(build.success ? "マシン情報を保存できませんでした。" : build.message)
        }

        setCreationStatus("building")
        setCreationMessage("マシンの生成・ビルドを受け付けました。")
        router.push(`/machines/${build.machineId}`)
      } catch (creationError) {
        console.error("Machine creation failed.", creationError)
        setCreationStatus("failed")
        setCreationMessage("")
        await markMachineCreationFailedAction(sessionId)
      } finally {
        creationStartedRef.current = false
      }
    },
    [answers, router, sessionId],
  )

  function handleMachineCreation() {
    void runMachineCreation(false)
  }

  function startEditing(targetStep: number) {
    setEditingStep(targetStep)
    setEditingError("")
  }

  async function completeEditing() {
    if (editingStep === null) return
    if (!isChatStepComplete(editingStep, answers)) {
      setEditingError(getChatValidationMessage(editingStep))
      return
    }
    if (!(await persistProgress(step, basicReady))) {
      setEditingError("変更を保存できませんでした。もう一度お試しください。")
      return
    }
    setEditingStep(null)
  }

  useEffect(() => {
    if (session.creationStatus === "generating_scenario") void runMachineCreation(true)
  }, [runMachineCreation, session.creationStatus])

  return (
    <div className="mx-auto flex h-[calc(100dvh-88px)] max-w-6xl min-h-0 flex-col max-lg:h-[calc(100dvh-64px)]">
      <section className="surface-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl">
        <div className="border-b border-[var(--line)] px-7 py-5 max-sm:px-5">
          <div className="flex items-center justify-between gap-5 max-sm:items-start">
            <div>
              <p className="mono-label mb-2 flex items-center gap-2 text-[var(--ink-soft)]">
                <span className="size-1.5 bg-[var(--accent)]" />
                Build session / {String(progress).padStart(2, "0")}
              </p>
              <div>
                <h1 className="display-heading text-[clamp(1.65rem,2.8vw,2.5rem)] leading-[1.08]">
                  マシン作成アシスタント
                </h1>
                <p className="mt-1.5 text-[0.9rem] font-semibold text-[var(--ink-soft)]">
                  {session.name}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3 max-sm:flex-col max-sm:items-end">
              <Link
                className="secondary-action inline-flex min-h-10 items-center rounded-lg px-4 text-[0.78rem] font-bold"
                href="/machines"
              >
                中止する
              </Link>
              <div className="grid gap-2">
                <span className="mono-label text-[var(--ink-soft)]">
                  {CHAT_COPY.progress} {progress} / {CHAT_STEPS.systemFlagDetails}
                </span>
                <div aria-hidden="true" className="flex gap-1">
                  {Array.from(
                    { length: CHAT_STEPS.systemFlagDetails },
                    (_, index) => index + 1,
                  ).map((segment) => (
                    <span className="step-block" data-active={segment <= progress} key={segment} />
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div
            aria-label={`ステップ ${progress} / ${CHAT_STEPS.systemFlagDetails}`}
            aria-valuemax={CHAT_STEPS.systemFlagDetails}
            aria-valuemin={CHAT_CONFIG.progressMinimum}
            aria-valuenow={progress}
            className="sr-only"
            role="progressbar"
          />
          <section className="mt-5 rounded-lg border border-[var(--line)] bg-[var(--surface-muted)]/55 px-4 py-3">
            <button
              aria-expanded={isSummaryOpen}
              className="flex w-full items-center justify-between text-left text-[0.82rem] font-bold text-[var(--ink-soft)] hover:text-[var(--ink)]"
              onClick={() => setIsSummaryOpen((open) => !open)}
              type="button"
            >
              <span>{CHAT_COPY.summary.title}</span>
              {isSummaryOpen ? (
                <ChevronUp aria-hidden="true" size={17} strokeWidth={2} />
              ) : (
                <ChevronDown aria-hidden="true" size={17} strokeWidth={2} />
              )}
            </button>
            {isSummaryOpen ? <AnswerSummary answers={answers} /> : null}
          </section>
        </div>

        <div
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-7 py-6 max-sm:px-5"
          ref={conversationRef}
        >
          <div className="grid gap-7">
            {transcript.map((message) => (
              <div className="grid gap-3" key={message.step}>
                <AssistantMessage prompt={message.prompt} />
                <UserMessage answer={message.answer} onEdit={() => startEditing(message.step)} />
                {editingStep === message.step ? (
                  <AnswerEditor
                    answers={answers}
                    error={editingError}
                    onChange={updateAnswers}
                    onComplete={completeEditing}
                    step={message.step}
                  />
                ) : null}
              </div>
            ))}
            <AssistantMessage current prompt={prompt} />
          </div>
        </div>

        <div className="border-t border-[var(--line)] bg-[var(--surface-muted)]/38 px-7 py-5 max-sm:px-5">
          {creationStatus === "input" && !basicReady && !isFinalStep ? (
            <StepInput answers={answers} onChange={updateAnswers} step={step} />
          ) : null}
          {error ? (
            <p className="mt-3 text-[0.86rem] font-bold text-[var(--danger)]">{error}</p>
          ) : null}
          {creationStatus !== "input" ? (
            <CreationStatusPanel
              machineId={session.machineId}
              message={creationMessage || "マシンを作成しています…"}
              onRetry={handleMachineCreation}
              status={creationStatus}
            />
          ) : basicReady ? (
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="primary-action inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
                disabled={isSaving}
                onClick={handleMachineCreation}
                type="button"
              >
                {CHAT_COPY.buttons.createBasic}
              </button>
              <button
                className="secondary-action inline-flex min-h-[46px] items-center justify-center rounded-lg px-[18px] text-[0.9rem] font-bold"
                disabled={isSaving}
                onClick={continueDetails}
                type="button"
              >
                {CHAT_COPY.buttons.continueDetails}
              </button>
            </div>
          ) : isFinalStep ? (
            <button
              className="primary-action mt-5 inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
              disabled={isSaving}
              onClick={handleMachineCreation}
              type="button"
            >
              {CHAT_COPY.buttons.createComplete}
            </button>
          ) : (
            <button
              className="primary-action mt-4 inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-4 text-[0.82rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
              disabled={isSaving}
              onClick={advance}
              type="button"
            >
              {isSaving ? (
                <>
                  <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
                  保存中…
                </>
              ) : step === CHAT_STEPS.difficulty ? (
                CHAT_COPY.buttons.setBasic
              ) : (
                <>
                  {CHAT_COPY.buttons.next}
                  <ArrowRight aria-hidden="true" size={16} strokeWidth={2} />
                </>
              )}
            </button>
          )}
        </div>
      </section>
    </div>
  )
}

function CreationStatusPanel({
  machineId,
  message,
  onRetry,
  status,
}: {
  machineId: string | null
  message: string
  onRetry: () => void
  status: ChatSession["creationStatus"]
}) {
  if (status === "building" || status === "completed") {
    return (
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[var(--line)] bg-[var(--success-soft)] p-4">
        <span className="flex items-center gap-2 text-[0.88rem] font-bold">
          <CheckCircle2 aria-hidden="true" className="text-[var(--success)]" size={18} />
          {status === "completed" ? "マシンのビルドが完了しました。" : message}
        </span>
        {machineId ? (
          <Link
            className="primary-action inline-flex min-h-10 items-center justify-center rounded-lg px-4 text-[0.82rem] font-bold"
            href={`/machines/${machineId}`}
          >
            マシンの状態を確認
          </Link>
        ) : null}
      </div>
    )
  }

  if (status === "failed") {
    return (
      <div className="mt-4 rounded-xl border border-[var(--danger)]/35 bg-[var(--danger-soft)] p-4">
        <p className="flex items-start gap-2 text-[0.88rem] font-bold text-[var(--danger)]">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
          マシンを作成できませんでした。
        </p>
        <button
          className="primary-action mt-4 inline-flex min-h-10 items-center justify-center rounded-lg px-4 text-[0.82rem] font-bold"
          onClick={onRetry}
          type="button"
        >
          もう一度試す
        </button>
      </div>
    )
  }

  return (
    <div className="mt-4 flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-4">
      <LoaderCircle aria-hidden="true" className="shrink-0 animate-spin" size={19} />
      <p className="text-[0.88rem] font-bold">{message}</p>
    </div>
  )
}

function AssistantMessage({
  current = false,
  prompt,
}: {
  current?: boolean
  prompt: { help: string; question: string }
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        aria-label={CHAT_COPY.assistantLabel}
        className="grid size-9 shrink-0 place-items-center rounded-lg border border-[var(--line)] bg-[var(--surface-muted)] text-[var(--signal)]"
        role="img"
      >
        <Bot aria-hidden="true" size={17} strokeWidth={1.8} />
      </span>
      <div
        className={`min-w-0 border-l-2 px-4 py-2 ${
          current ? "border-[var(--signal)] bg-[var(--signal-soft)]/24" : "border-[var(--line)]"
        }`}
      >
        <p className="mono-label mb-1.5 text-[0.62rem] text-[var(--ink-faint)]">SLSG / assistant</p>
        <h2 className="text-[1rem] font-bold tracking-[-0.02em]">{prompt.question}</h2>
        {prompt.help ? (
          <p className="mt-1.5 text-[0.88rem] leading-[1.6] text-[var(--ink-soft)]">
            {prompt.help}
          </p>
        ) : null}
      </div>
    </div>
  )
}

function UserMessage({ answer, onEdit }: { answer: string; onEdit: () => void }) {
  return (
    <div className="ml-auto flex max-w-[80%] flex-col items-end gap-1">
      <div className="signal-corner w-full rounded-xl bg-[var(--inverse-surface)] px-4 py-3 text-[var(--inverse-ink)]">
        <span className="text-[0.68rem] font-bold tracking-wide text-[var(--surface-strong)]">
          {CHAT_COPY.userLabel}
        </span>
        <p className="mt-1 text-[0.9rem] leading-[1.55]">{answer}</p>
      </div>
      <button
        aria-label="この回答を編集"
        className="inline-flex size-7 items-center justify-center rounded-md text-[var(--ink-soft)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]"
        onClick={onEdit}
        type="button"
      >
        <Pencil aria-hidden="true" size={14} strokeWidth={2} />
      </button>
    </div>
  )
}

function AnswerEditor({
  answers,
  error,
  onChange,
  onComplete,
  step,
}: {
  answers: ChatAnswers
  error: string
  onChange: (values: Partial<ChatAnswers>) => void
  onComplete: () => void
  step: number
}) {
  return (
    <div className="surface-panel ml-auto grid w-full max-w-[80%] gap-4 rounded-xl p-4">
      <p className="text-[0.82rem] font-extrabold">回答を編集</p>
      <StepInput answers={answers} onChange={onChange} step={step} />
      {error ? <p className="text-[0.86rem] font-bold text-[var(--danger)]">{error}</p> : null}
      <button
        className="primary-action inline-flex min-h-[46px] w-fit items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
        onClick={onComplete}
        type="button"
      >
        更新
      </button>
    </div>
  )
}

type StepInputProps = {
  answers: ChatAnswers
  onChange: (values: Partial<ChatAnswers>) => void
  step: number
}

function StepInput({ answers, onChange, step }: StepInputProps) {
  if (step === CHAT_STEPS.machineName) {
    return (
      <label className="grid gap-2 text-[0.86rem] font-bold">
        <span>{CHAT_COPY.fields.machineName}</span>
        <input
          className="field-control w-full rounded-lg px-[14px] py-[13px] placeholder:text-[var(--ink-faint)]"
          maxLength={CHAT_CONFIG.machineNameMaxLength}
          onChange={(event) => onChange({ name: event.target.value })}
          placeholder={CHAT_COPY.fields.machineNamePlaceholder}
          value={answers.name}
        />
        <small className="text-right font-mono text-[0.72rem] font-normal text-[var(--ink-soft)]">
          {answers.name.length} / {CHAT_CONFIG.machineNameMaxLength}
        </small>
      </label>
    )
  }
  if (step === CHAT_STEPS.visibility) {
    return (
      <OptionButtons
        onSelect={(visibility) => onChange({ visibility })}
        options={VISIBILITY_OPTIONS}
        value={answers.visibility}
      />
    )
  }
  if (step === CHAT_STEPS.theme) {
    return (
      <div className="grid gap-3">
        <div className="flex flex-wrap gap-2">
          {THEME_SUGGESTIONS.map((theme) => (
            <button
              className={`rounded-md border px-3 py-2 text-[0.78rem] font-bold transition ${
                answers.theme === theme
                  ? "border-[var(--signal-solid)] bg-[var(--signal-solid)] text-[var(--inverse-ink)]"
                  : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--signal)]"
              }`}
              key={theme}
              onClick={() => onChange({ theme })}
              type="button"
            >
              {theme}
            </button>
          ))}
        </div>
        <label className="grid gap-2 text-[0.86rem] font-bold">
          <span>{CHAT_COPY.fields.freeInput}</span>
          <input
            className="field-control w-full rounded-lg px-[14px] py-[13px] placeholder:text-[var(--ink-faint)]"
            onChange={(event) => onChange({ theme: event.target.value })}
            placeholder={CHAT_COPY.fields.themePlaceholder}
            value={answers.theme}
          />
        </label>
      </div>
    )
  }
  if (step === CHAT_STEPS.difficulty) {
    return (
      <OptionButtons
        onSelect={(difficulty) => onChange({ difficulty })}
        options={DIFFICULTY_OPTIONS}
        value={answers.difficulty}
      />
    )
  }
  if (step === CHAT_STEPS.userFlagChoice) {
    return (
      <YesNoButtons
        onSelect={(needsUserFlag) => onChange({ needsUserFlag })}
        value={answers.needsUserFlag}
      />
    )
  }
  if (step === CHAT_STEPS.userFlagDetails) {
    return (
      <DetailInput
        label={CHAT_COPY.fields.userFlagDetails}
        onChange={(userFlagDetails) => onChange({ userFlagDetails })}
        placeholder={CHAT_COPY.fields.userFlagDetailsPlaceholder}
        value={answers.userFlagDetails}
      />
    )
  }
  if (step === CHAT_STEPS.systemFlagChoice) {
    return (
      <YesNoButtons
        onSelect={(needsSystemFlag) => onChange({ needsSystemFlag })}
        value={answers.needsSystemFlag}
      />
    )
  }
  return (
    <DetailInput
      label={CHAT_COPY.fields.systemFlagDetails}
      onChange={(systemFlagDetails) => onChange({ systemFlagDetails })}
      placeholder={CHAT_COPY.fields.systemFlagDetailsPlaceholder}
      value={answers.systemFlagDetails}
    />
  )
}

function DetailInput({
  label,
  onChange,
  placeholder,
  value,
}: {
  label: string
  onChange: (value: string) => void
  placeholder: string
  value: string
}) {
  return (
    <label className="grid gap-2 text-[0.86rem] font-bold">
      <span>{label}</span>
      <textarea
        className="field-control min-h-28 w-full resize-y rounded-lg px-[14px] py-[13px] placeholder:text-[var(--ink-faint)]"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
    </label>
  )
}

function OptionButtons<T extends string>({
  onSelect,
  options,
  value,
}: {
  onSelect: (value: T) => void
  options: readonly T[]
  value: T | ""
}) {
  return (
    <div className="grid grid-cols-2 gap-2.5 max-sm:grid-cols-1">
      {options.map((option) => (
        <button
          className={`min-h-11 rounded-lg border px-3 text-left text-[0.82rem] font-bold transition ${
            value === option
              ? "border-[var(--signal-solid)] bg-[var(--signal-solid)] text-[var(--inverse-ink)]"
              : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--signal)]"
          }`}
          key={option}
          onClick={() => onSelect(option)}
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  )
}

function YesNoButtons({
  onSelect,
  value,
}: {
  onSelect: (value: boolean) => void
  value: boolean | null
}) {
  return (
    <div className="grid grid-cols-2 gap-2.5 max-sm:grid-cols-1">
      <button
        className={`min-h-11 rounded-lg border px-3 text-left text-[0.82rem] font-bold transition ${
          value === true
            ? "border-[var(--signal-solid)] bg-[var(--signal-solid)] text-[var(--inverse-ink)]"
            : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--signal)]"
        }`}
        onClick={() => onSelect(true)}
        type="button"
      >
        {CHAT_COPY.yesNo.yes}
      </button>
      <button
        className={`min-h-11 rounded-lg border px-3 text-left text-[0.82rem] font-bold transition ${
          value === false
            ? "border-[var(--signal-solid)] bg-[var(--signal-solid)] text-[var(--inverse-ink)]"
            : "border-[var(--line)] bg-[var(--surface)] hover:border-[var(--signal)]"
        }`}
        onClick={() => onSelect(false)}
        type="button"
      >
        {CHAT_COPY.yesNo.no}
      </button>
    </div>
  )
}

function AnswerSummary({ answers }: { answers: ChatAnswers }) {
  return (
    <dl className="mt-4 grid grid-cols-2 gap-3 max-sm:grid-cols-1">
      {buildChatSummary(answers).map(([label, value]) => (
        <div className="rounded-lg border border-[var(--line)] bg-[var(--surface)] p-3" key={label}>
          <dt className="text-[0.72rem] font-bold text-[var(--ink-soft)]">{label}</dt>
          <dd className="mt-1 text-[0.88rem] font-bold">{value || CHAT_COPY.summary.empty}</dd>
        </div>
      ))}
    </dl>
  )
}

export function MissingChatSession() {
  return (
    <section className="surface-panel grid gap-4 rounded-2xl p-8">
      <h1 className="display-heading text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05]">
        {CHAT_COPY.missingSession.title}
      </h1>
      <p className="leading-[1.65] text-[var(--ink-soft)]">{CHAT_COPY.missingSession.message}</p>
      <Link
        className="primary-action inline-flex min-h-[46px] w-fit items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
        href={CHAT_CONFIG.newChatPath}
      >
        {CHAT_COPY.missingSession.action}
      </Link>
    </section>
  )
}
