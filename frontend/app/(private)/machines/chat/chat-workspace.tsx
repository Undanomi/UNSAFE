"use client"

import {
  AlertCircle,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  LoaderCircle,
  Pencil,
  XCircle,
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { type KeyboardEvent, useCallback, useEffect, useId, useRef, useState } from "react"
import {
  cancelMachineCreationAction,
  markMachineCreationFailedAction,
  markMachineCreationReadyAction,
  prepareMachineCreationAction,
  saveChatProgressAction,
  startMachineBuildAction,
} from "@/app/actions/chat"
import { TerminalTelemetry } from "@/components/terminal-telemetry"
import {
  CHAT_CONFIG,
  CHAT_COPY,
  CHAT_PROMPTS,
  CHAT_STEPS,
  type ChatAnswers,
  type ChatCreationFailure,
  type ChatSession,
  DIFFICULTY_OPTIONS,
  EMPTY_CHAT_ANSWERS,
  SCENARIO_PROMPT_SUGGESTIONS,
  VISIBILITY_OPTIONS,
} from "@/stores/chat"

type ChatWorkspaceProps = {
  session: ChatSession
}

type ScenarioEvent = {
  event: string
  data: unknown
}

type AutomaticFlagSelection = "user" | "system" | "both"

const SCENARIO_STREAM_MAX_ATTEMPTS = 3
const SCENARIO_STREAM_RETRY_DELAY_MS = 500

class ScenarioGenerationFailedError extends Error {}
class ScenarioGenerationCancelledError extends Error {}

class ScenarioInputRevisionRequiredError extends Error {
  suggestions: string[]

  constructor(summary: string, suggestions: string[]) {
    super(summary)
    this.name = "ScenarioInputRevisionRequiredError"
    this.suggestions = suggestions
  }
}

function readInputRevisionError(data: unknown): ScenarioInputRevisionRequiredError | null {
  if (!data || typeof data !== "object" || !("code" in data)) return null
  if (data.code !== "scenario_input_revision_required") return null
  const summary =
    "summary" in data && typeof data.summary === "string"
      ? data.summary
      : "入力された条件では、成立するシナリオを構成できませんでした。"
  const findings = "findings" in data && Array.isArray(data.findings) ? data.findings : []
  const suggestions = findings.flatMap((finding) => {
    if (!finding || typeof finding !== "object" || !("remediation" in finding)) return []
    return typeof finding.remediation === "string" ? [finding.remediation] : []
  })
  return new ScenarioInputRevisionRequiredError(summary, suggestions)
}

function readScenarioId(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("scenario" in data)) return null
  const scenario = data.scenario
  if (!scenario || typeof scenario !== "object" || !("scenario_id" in scenario)) return null
  return typeof scenario.scenario_id === "string" ? scenario.scenario_id : null
}

function readAutomaticFlagSelection(data: unknown): AutomaticFlagSelection | null {
  if (!data || typeof data !== "object" || !("selection" in data)) return null
  const selection = data.selection
  return selection === "user" || selection === "system" || selection === "both" ? selection : null
}

async function consumeScenarioStream(
  response: Response,
  onProgress: (generatedCharacters: number) => void,
  onFlagsPlanned: (selection: AutomaticFlagSelection) => void,
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
      if (parsed.event === "scenario.flags_planned") {
        const selection = readAutomaticFlagSelection(parsed.data)
        if (selection) onFlagsPlanned(selection)
      }
      if (parsed.event === "scenario.delta") {
        const content =
          parsed.data && typeof parsed.data === "object" && "content" in parsed.data
            ? parsed.data.content
            : ""
        generatedCharacters += typeof content === "string" ? content.length : 0
        onProgress(generatedCharacters)
      }
      if (parsed.event === "scenario.error") {
        const revisionError = readInputRevisionError(parsed.data)
        if (revisionError) throw revisionError
        throw new ScenarioGenerationFailedError("シナリオ生成に失敗しました。")
      }
      if (parsed.event === "scenario.cancelled") {
        throw new ScenarioGenerationCancelledError("マシン作成は中止されました。")
      }
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

async function waitForScenario(
  sessionId: string,
  onProgress: (generatedCharacters: number) => void,
  onFlagsPlanned: (selection: AutomaticFlagSelection) => void,
  signal: AbortSignal,
): Promise<string> {
  let lastError: unknown
  for (let attempt = 1; attempt <= SCENARIO_STREAM_MAX_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(`/api/chat/${encodeURIComponent(sessionId)}/scenario`, {
        cache: "no-store",
        signal,
      })
      return await consumeScenarioStream(response, onProgress, onFlagsPlanned)
    } catch (error) {
      if (
        error instanceof ScenarioGenerationFailedError ||
        error instanceof ScenarioInputRevisionRequiredError ||
        error instanceof ScenarioGenerationCancelledError ||
        signal.aborted
      )
        throw error
      lastError = error
      if (attempt < SCENARIO_STREAM_MAX_ATTEMPTS) {
        await new Promise((resolve) => setTimeout(resolve, SCENARIO_STREAM_RETRY_DELAY_MS))
        if (signal.aborted) throw signal.reason
      }
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("AIサーバーとの接続が途中で終了しました。")
}

function buildInitialAnswers(session: ChatSession): ChatAnswers {
  const answers = { ...EMPTY_CHAT_ANSWERS, ...session.initialAnswers }
  return {
    ...answers,
    name: answers.name.slice(0, CHAT_CONFIG.machineNameMaxLength),
    theme: answers.theme.slice(0, CHAT_CONFIG.scenarioPromptMaxLength),
  }
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

function isTextInputStep(step: number) {
  return (
    step === CHAT_STEPS.machineName ||
    step === CHAT_STEPS.theme ||
    step === CHAT_STEPS.userFlagDetails ||
    step === CHAT_STEPS.systemFlagDetails
  )
}

function getFlagDetailsStep(step: number, answers: ChatAnswers) {
  if (step === CHAT_STEPS.userFlagChoice && answers.needsUserFlag === true) {
    return CHAT_STEPS.userFlagDetails
  }
  if (step === CHAT_STEPS.systemFlagChoice && answers.needsSystemFlag === true) {
    return CHAT_STEPS.systemFlagDetails
  }
  return null
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
  const [creationFailure, setCreationFailure] = useState<ChatCreationFailure | null>(
    session.creationFailure,
  )
  const [error, setError] = useState("")
  const [editingStep, setEditingStep] = useState<number | null>(null)
  const [editingError, setEditingError] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isConfirmingCancel, setIsConfirmingCancel] = useState(false)
  const [cancelDialogError, setCancelDialogError] = useState("")
  const [showRebuildButton, setShowRebuildButton] = useState(false)
  const conversationRef = useRef<HTMLDivElement>(null)
  const editingAnswersSnapshotRef = useRef<ChatAnswers | null>(null)
  const creationStartedRef = useRef(false)
  const creationAbortRef = useRef<AbortController | null>(null)
  const cancellationRequestedRef = useRef(false)
  const cancelDialogRef = useRef<HTMLDialogElement>(null)
  const cancelConfirmingRef = useRef(false)
  const choiceSubmissionRef = useRef(false)
  const progressSavingRef = useRef(false)

  const progress = Math.min(step, CHAT_STEPS.systemFlagDetails)
  const isFinalStep = step === CHAT_STEPS.complete
  const prompt = getChatPrompt(step, basicReady)
  const transcriptStep = editingStep === null ? step : Math.max(step, editingStep + 1)
  const transcript = buildChatTranscript(transcriptStep, basicReady, answers)
  const chatProgress = `${step}:${basicReady}`

  useEffect(() => {
    if (!chatProgress) return
    choiceSubmissionRef.current = false
  }, [chatProgress])

  useEffect(() => {
    if (!chatProgress) return
    const conversation = conversationRef.current
    if (conversation) {
      conversation.scrollTo({
        behavior: "smooth",
        top: conversation.scrollHeight,
      })
    }
  }, [chatProgress])

  function updateAnswers(values: Partial<ChatAnswers>) {
    setAnswers((current) => ({ ...current, ...values }))
    setError("")
    setEditingError("")
  }

  async function persistProgress(
    nextStep: number,
    nextBasicReady: boolean,
    answersToSave: ChatAnswers = answers,
  ) {
    if (progressSavingRef.current) return false
    progressSavingRef.current = true
    setIsSaving(true)
    try {
      const result = await saveChatProgressAction({
        sessionId,
        answers: answersToSave,
        currentStep: nextStep,
        basicReady: nextBasicReady,
      })
      if (!result.success) {
        setError(result.message)
        return false
      }

      if (!sessionId) {
        setSessionId(result.sessionId)
        router.replace(`/machines/chat/${result.sessionId}`)
      }
      return true
    } catch {
      setError("回答を保存できませんでした。もう一度お試しください。")
      return false
    } finally {
      progressSavingRef.current = false
      setIsSaving(false)
    }
  }

  async function selectChoice(values: Partial<ChatAnswers>) {
    if (choiceSubmissionRef.current || isSaving) return
    choiceSubmissionRef.current = true
    const selectedAnswers = { ...answers, ...values }
    setAnswers(selectedAnswers)
    setError("")

    const nextBasicReady = step === CHAT_STEPS.difficulty
    const nextStep = nextBasicReady ? step : getNextChatStep(step, selectedAnswers)
    if (!(await persistProgress(nextStep, nextBasicReady, selectedAnswers))) {
      choiceSubmissionRef.current = false
      return
    }
    if (nextBasicReady) setBasicReady(true)
    else setStep(nextStep)
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
      cancellationRequestedRef.current = false
      const abortController = new AbortController()
      creationAbortRef.current = abortController
      setCreationStatus("generating_scenario")
      setCreationMessage("AIにマシン設定を送信しています…")
      setCreationFailure(null)
      setError("")

      try {
        if (!resume) {
          const preparation = await prepareMachineCreationAction(sessionId, answers)
          if (!preparation.success) throw new Error(preparation.message)
          if (cancellationRequestedRef.current) {
            await cancelMachineCreationAction(sessionId)
            return
          }
        }

        setCreationMessage("AIがシナリオを生成しています…")
        const scenarioId = await waitForScenario(
          sessionId,
          (characters) => {
            setCreationMessage(`AIがシナリオを生成しています… ${characters.toLocaleString()}文字`)
          },
          (selection) => {
            const label =
              selection === "user"
                ? "ユーザーフラグのみ"
                : selection === "system"
                  ? "システムフラグのみ"
                  : "ユーザー・システムフラグの両方"
            setCreationMessage(`AIが「${label}」を選択しました。シナリオを生成しています…`)
          },
          abortController.signal,
        )

        if (cancellationRequestedRef.current) {
          await cancelMachineCreationAction(sessionId)
          return
        }

        setCreationMessage("シナリオが完成しました。ビルドを開始しています…")
        const build = await startMachineBuildAction(sessionId, scenarioId)
        if (cancellationRequestedRef.current) {
          await cancelMachineCreationAction(sessionId)
          return
        }
        if (!build.success || !build.machineId) {
          throw new Error(build.success ? "マシン情報を保存できませんでした。" : build.message)
        }

        setCreationStatus("building")
        setCreationMessage("マシンの生成・ビルドを受け付けました。")
        router.push(`/machines/${build.machineId}`)
      } catch (creationError) {
        if (
          cancellationRequestedRef.current ||
          abortController.signal.aborted ||
          creationError instanceof ScenarioGenerationCancelledError
        ) {
          return
        }
        console.error("Machine creation failed.", creationError)
        const failure: ChatCreationFailure =
          creationError instanceof ScenarioInputRevisionRequiredError
            ? {
                kind: "settings",
                summary: creationError.message,
                suggestions: creationError.suggestions,
              }
            : {
                kind: "system",
                summary: "マシンを作成できませんでした。",
                suggestions: [],
              }
        setCreationStatus("failed")
        setCreationMessage("")
        setCreationFailure(failure)
        await markMachineCreationFailedAction(sessionId, failure)
      } finally {
        if (creationAbortRef.current === abortController) creationAbortRef.current = null
        creationStartedRef.current = false
      }
    },
    [answers, router, sessionId],
  )

  function handleMachineCreation() {
    void runMachineCreation(false)
  }

  async function handleCancel() {
    if (creationStatus === "completed") return false
    if (!sessionId || creationStatus === "input") {
      router.push("/machines")
      return true
    }

    if (!(await cancelActiveCreation())) return false
    router.push("/machines")
    router.refresh()
    return true
  }

  async function confirmCancel() {
    if (cancelConfirmingRef.current) return
    cancelConfirmingRef.current = true
    setIsConfirmingCancel(true)
    setCancelDialogError("")
    try {
      if (await handleCancel()) cancelDialogRef.current?.close()
      else setCancelDialogError("中止できませんでした。もう一度お試しください。")
    } catch {
      setCancelDialogError("中止できませんでした。もう一度お試しください。")
    } finally {
      cancelConfirmingRef.current = false
      setIsConfirmingCancel(false)
    }
  }

  async function cancelActiveCreation() {
    if (!sessionId || creationStatus === "completed") return false
    const previousCreationStatus = creationStatus
    const previousCreationMessage = creationMessage
    cancellationRequestedRef.current = true
    creationAbortRef.current?.abort()
    setIsCancelling(true)
    setCreationStatus("cancelled")
    setCreationMessage("")
    setCreationFailure(null)
    setError("")
    let cancelError = "中止できませんでした。もう一度お試しください。"
    try {
      const result = await cancelMachineCreationAction(sessionId)
      if (result.success) return true
      cancelError = result.message
    } catch {
      // Restore the chat state so the user can retry the cancellation.
    } finally {
      setIsCancelling(false)
    }

    cancellationRequestedRef.current = false
    setCreationStatus(previousCreationStatus)
    setCreationMessage(previousCreationMessage)
    setError(cancelError)
    return false
  }

  async function startEditing(targetStep: number) {
    if (
      sessionId &&
      (creationStatus === "generating_scenario" || creationStatus === "building") &&
      !(await cancelActiveCreation())
    ) {
      return
    }
    editingAnswersSnapshotRef.current = answers
    setEditingStep(targetStep)
    setEditingError("")
  }

  function cancelEditing() {
    const previousAnswers = editingAnswersSnapshotRef.current
    if (previousAnswers) setAnswers(previousAnswers)
    editingAnswersSnapshotRef.current = null
    setEditingStep(null)
    setEditingError("")
  }

  async function completeEditing() {
    if (editingStep === null) return
    if (!isChatStepComplete(editingStep, answers)) {
      setEditingError(getChatValidationMessage(editingStep))
      return
    }
    const flagDetailsStep = getFlagDetailsStep(editingStep, answers)
    if (flagDetailsStep !== null) {
      setEditingStep(flagDetailsStep)
      setEditingError("")
      return
    }
    if (!(await persistProgress(step, basicReady))) {
      setEditingError("変更を保存できませんでした。もう一度お試しください。")
      return
    }
    if (sessionId) {
      const ready = await markMachineCreationReadyAction(sessionId)
      if (!ready.success) {
        setEditingError(ready.message)
        return
      }
    }
    setCreationStatus("input")
    setCreationMessage("")
    setCreationFailure(null)
    setShowRebuildButton(true)
    editingAnswersSnapshotRef.current = null
    setEditingStep(null)
  }

  return (
    <div className="slsg-chat-workspace">
      <header className="slsg-chat-header">
        <h1 className="sr-only">マシン作成チャット</h1>
        <div className="slsg-chat-panel-header">
          <span className="slsg-chat-progress-copy">
            {CHAT_COPY.progress} {progress} / {CHAT_STEPS.systemFlagDetails}
          </span>
          <ChatProgress progress={progress} />
          <button
            className="slsg-chat-cancel"
            disabled={isCancelling || isConfirmingCancel || creationStatus === "completed"}
            onClick={() => {
              setCancelDialogError("")
              cancelDialogRef.current?.showModal()
            }}
            type="button"
          >
            {isCancelling || isConfirmingCancel ? "中止しています…" : "中止する"}
          </button>
        </div>
      </header>

      <div className="slsg-chat-layout">
        <section className="slsg-chat-conversation">
          <div className="slsg-chat-conversation-inner">
            <div className="slsg-chat-panel-body">
              <div className="slsg-chat-message-list" ref={conversationRef}>
                {transcript.map((message) => (
                  <article className="slsg-chat-message" key={message.step}>
                    <AssistantMessage prompt={message.prompt} />
                    <UserMessage
                      answer={message.answer}
                      disabled={isCancelling}
                      onEdit={() => void startEditing(message.step)}
                    />
                    {editingStep === message.step ? (
                      <AnswerEditor
                        actionLabel={
                          getFlagDetailsStep(message.step, answers) === null ? "更新" : "次へ"
                        }
                        answers={answers}
                        error={editingError}
                        onCancel={cancelEditing}
                        onChange={updateAnswers}
                        onComplete={completeEditing}
                        step={message.step}
                      />
                    ) : null}
                  </article>
                ))}
                <article className="slsg-chat-message is-current">
                  <AssistantMessage prompt={prompt} />
                </article>
              </div>

              <div className="slsg-chat-composer">
                {creationStatus === "input" && !basicReady && !isFinalStep ? (
                  <div className="slsg-chat-current-input">
                    <StepInput
                      answers={answers}
                      choicesDisabled={isSaving}
                      inlineSubmit={isTextInputStep(step) && step !== CHAT_STEPS.machineName}
                      onChange={updateAnswers}
                      onChoiceSelect={(values) => void selectChoice(values)}
                      onSubmit={() => void advance()}
                      step={step}
                      submitting={isSaving}
                    />
                    {step === CHAT_STEPS.machineName ? (
                      <ChatSendButton
                        disabled={isSaving}
                        onSubmit={advance}
                        submitting={isSaving}
                      />
                    ) : null}
                  </div>
                ) : null}
                {error ? <p className="slsg-chat-error">{error}</p> : null}

                {creationStatus !== "input" || basicReady || isFinalStep ? (
                  <div className="slsg-chat-actions">
                    {creationStatus !== "input" ? (
                      <CreationStatusPanel
                        failure={creationFailure}
                        machineId={session.machineId}
                        message={creationMessage || "マシンを作成しています…"}
                        onRetry={handleMachineCreation}
                        status={creationStatus}
                      />
                    ) : basicReady ? (
                      <div className="slsg-chat-actions-group">
                        <button
                          className="slsg-chat-action-primary"
                          disabled={isSaving}
                          onClick={handleMachineCreation}
                          type="button"
                        >
                          {showRebuildButton
                            ? "改めてマシンをビルドする"
                            : CHAT_COPY.buttons.createBasic}
                        </button>
                        <button
                          className="slsg-chat-action-secondary"
                          disabled={isSaving}
                          onClick={continueDetails}
                          type="button"
                        >
                          {CHAT_COPY.buttons.continueDetails}
                        </button>
                      </div>
                    ) : isFinalStep ? (
                      <button
                        className="slsg-chat-action-primary"
                        disabled={isSaving}
                        onClick={handleMachineCreation}
                        type="button"
                      >
                        {showRebuildButton
                          ? "改めてマシンをビルドする"
                          : CHAT_COPY.buttons.createComplete}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </section>
      </div>
      <dialog
        aria-describedby="slsg-chat-cancel-description"
        aria-labelledby="slsg-chat-cancel-title"
        className="slsg-chat-cancel-dialog"
        onCancel={(event) => {
          if (cancelConfirmingRef.current) event.preventDefault()
        }}
        onClose={() => setCancelDialogError("")}
        ref={cancelDialogRef}
      >
        <h2 id="slsg-chat-cancel-title">作成を中止しますか？</h2>
        <p id="slsg-chat-cancel-description">
          マシン一覧に戻ります。生成中の処理がある場合は停止します。
        </p>
        {cancelDialogError ? (
          <p className="slsg-chat-cancel-dialog-error" role="alert">
            {cancelDialogError}
          </p>
        ) : null}
        <div className="slsg-chat-cancel-dialog-actions">
          <button
            className="slsg-chat-action-secondary"
            disabled={isConfirmingCancel}
            onClick={() => cancelDialogRef.current?.close()}
            type="button"
          >
            続ける
          </button>
          <button
            className="slsg-chat-action-primary"
            disabled={isConfirmingCancel}
            onClick={() => void confirmCancel()}
            type="button"
          >
            {isConfirmingCancel ? "中止しています…" : "中止する"}
          </button>
        </div>
      </dialog>
      <TerminalTelemetry />
    </div>
  )
}

function ChatProgress({ progress }: { progress: number }) {
  return (
    <div
      aria-label={`ステップ ${progress} / ${CHAT_STEPS.systemFlagDetails}`}
      aria-valuemax={CHAT_STEPS.systemFlagDetails}
      aria-valuemin={CHAT_CONFIG.progressMinimum}
      aria-valuenow={progress}
      className="slsg-chat-progress"
      role="progressbar"
    >
      {Array.from({ length: CHAT_STEPS.systemFlagDetails }, (_, index) => index + 1).map(
        (stepNumber, index) => (
          <div className="slsg-chat-progress-segment" key={stepNumber}>
            <span
              className={`slsg-chat-progress-node ${
                stepNumber < progress
                  ? "is-completed"
                  : stepNumber === progress
                    ? "is-current"
                    : "is-upcoming"
              }`}
            >
              {stepNumber < progress ? <Check aria-hidden="true" size={15} /> : stepNumber}
            </span>
            {index < CHAT_STEPS.systemFlagDetails - 1 ? (
              <span
                className={`slsg-chat-progress-line ${stepNumber < progress ? "is-completed" : ""}`}
              />
            ) : null}
          </div>
        ),
      )}
    </div>
  )
}

function CreationStatusPanel({
  failure,
  machineId,
  message,
  onRetry,
  status,
}: {
  failure: ChatCreationFailure | null
  machineId: string | null
  message: string
  onRetry: () => void
  status: ChatSession["creationStatus"]
}) {
  if (status === "building" || status === "completed") {
    return (
      <div className="slsg-chat-creation-status is-success">
        <span className="flex items-center gap-2 text-[0.88rem] font-bold">
          <CheckCircle2 aria-hidden="true" size={18} />
          {status === "completed" ? "マシンのビルドが完了しました。" : message}
        </span>
        {machineId ? (
          <Link className="slsg-chat-status-action" href={`/machines/${machineId}`}>
            マシンの状態を確認
          </Link>
        ) : null}
      </div>
    )
  }

  if (status === "failed") {
    const revisionFailure = failure?.kind === "settings" ? failure : null
    const safetyRefused = failure?.kind === "ai_safety_refusal"
    return (
      <div className="slsg-chat-creation-status is-failed">
        <p className="flex items-start gap-2 text-[0.88rem] font-bold">
          <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
          {revisionFailure
            ? "問題設定の見直しが必要です。"
            : safetyRefused
              ? "安全上の理由でAIが処理を拒否しました"
              : "マシンを作成できませんでした。"}
        </p>
        {revisionFailure ? (
          <div className="slsg-chat-failure-details">
            <p>{revisionFailure.summary}</p>
            {revisionFailure.suggestions.length > 0 ? (
              <ul className="list-disc space-y-2 pl-5">
                {revisionFailure.suggestions.map((suggestion) => (
                  <li key={suggestion}>{suggestion}</li>
                ))}
              </ul>
            ) : null}
            <p>
              上の回答にある鉛筆ボタンから、指摘された入力条件の矛盾を解消してから再生成してください。
            </p>
          </div>
        ) : null}
        {safetyRefused ? (
          <div className="slsg-chat-failure-details">
            <p>{failure.summary}</p>
            <p>このマシンの処理は停止しました。同じ設定のまま再生成することはできません。</p>
          </div>
        ) : null}
        {!safetyRefused ? (
          <button className="slsg-chat-status-action" onClick={onRetry} type="button">
            {revisionFailure ? "修正した設定で再生成する" : "もう一度試す"}
          </button>
        ) : null}
      </div>
    )
  }

  if (status === "cancelled") {
    return (
      <div className="slsg-chat-creation-status is-cancelled">
        <p className="flex items-center gap-2 text-[0.88rem] font-bold">
          <XCircle aria-hidden="true" size={18} />
          マシン作成を中止しました。
        </p>
        <button className="slsg-chat-status-action" onClick={onRetry} type="button">
          もう一度作成する
        </button>
      </div>
    )
  }

  return (
    <div className="slsg-chat-creation-status is-building">
      <LoaderCircle aria-hidden="true" className="shrink-0 animate-spin" size={19} />
      <p className="text-[0.88rem] font-bold">{message}</p>
    </div>
  )
}

function AssistantMessage({ prompt }: { prompt: { help: string; question: string } }) {
  return (
    <div className="slsg-chat-assistant">
      <span aria-label="UNSAFEチャットボット" className="slsg-chat-assistant-avatar" role="img">
        <Bot aria-hidden="true" size={23} strokeWidth={1.8} />
      </span>
      <div className="slsg-chat-assistant-content">
        <span className="slsg-chat-assistant-name">UNSAFE</span>
        <h2>{prompt.question}</h2>
        {prompt.help ? <p>{prompt.help}</p> : null}
      </div>
    </div>
  )
}

function UserMessage({
  answer,
  disabled,
  onEdit,
}: {
  answer: string
  disabled: boolean
  onEdit: () => void
}) {
  return (
    <div className="slsg-chat-answer">
      <p>{answer}</p>
      <button
        aria-label="この回答を編集"
        className="slsg-chat-edit-button"
        disabled={disabled}
        onClick={onEdit}
        type="button"
      >
        <Pencil aria-hidden="true" size={18} strokeWidth={1.8} />
        編集
      </button>
    </div>
  )
}

function AnswerEditor({
  actionLabel,
  answers,
  error,
  onCancel,
  onChange,
  onComplete,
  step,
}: {
  actionLabel: "更新" | "次へ"
  answers: ChatAnswers
  error: string
  onCancel: () => void
  onChange: (values: Partial<ChatAnswers>) => void
  onComplete: () => void
  step: number
}) {
  return (
    <div className="slsg-chat-answer-editor">
      <p>回答を編集</p>
      <StepInput answers={answers} onChange={onChange} onSubmit={onComplete} step={step} />
      {error ? <p className="slsg-chat-error">{error}</p> : null}
      <div className="slsg-chat-answer-editor-actions">
        <button className="slsg-chat-action-secondary is-compact" onClick={onCancel} type="button">
          取り消す
        </button>
        <button className="slsg-chat-action-primary is-compact" onClick={onComplete} type="button">
          {actionLabel}
        </button>
      </div>
    </div>
  )
}

type StepInputProps = {
  answers: ChatAnswers
  choicesDisabled?: boolean
  inlineSubmit?: boolean
  onChange: (values: Partial<ChatAnswers>) => void
  onChoiceSelect?: (values: Partial<ChatAnswers>) => void
  onSubmit?: () => void
  step: number
  submitting?: boolean
}

function ChatSendButton({
  disabled = false,
  onSubmit,
  submitting = false,
}: {
  disabled?: boolean
  onSubmit: () => void
  submitting?: boolean
}) {
  return (
    <button
      aria-label={CHAT_COPY.buttons.next}
      className="slsg-chat-send-button"
      disabled={disabled}
      onClick={onSubmit}
      type="button"
    >
      {submitting ? (
        <LoaderCircle aria-hidden="true" className="animate-spin" size={19} />
      ) : (
        <ArrowRight aria-hidden="true" size={20} strokeWidth={2} />
      )}
    </button>
  )
}

function submitChatInputOnEnter(
  event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
  onSubmit?: () => void,
) {
  if (
    event.key !== "Enter" ||
    event.shiftKey ||
    event.nativeEvent.isComposing ||
    onSubmit === undefined
  ) {
    return
  }

  event.preventDefault()
  onSubmit()
}

function limitChatInputValue(input: HTMLInputElement | HTMLTextAreaElement, maxLength: number) {
  const value = input.value.slice(0, maxLength)
  if (input.value !== value) input.value = value
  return value
}

function StepInput({
  answers,
  choicesDisabled = false,
  inlineSubmit = false,
  onChange,
  onChoiceSelect,
  onSubmit,
  step,
  submitting = false,
}: StepInputProps) {
  const selectChoice = onChoiceSelect ?? onChange
  const updateMachineName = (input: HTMLInputElement) => {
    onChange({ name: limitChatInputValue(input, CHAT_CONFIG.machineNameMaxLength) })
  }

  if (step === CHAT_STEPS.machineName) {
    return (
      <label className="slsg-chat-field">
        <span className="sr-only">{CHAT_COPY.fields.machineName}</span>
        <input
          className="slsg-input slsg-chat-input"
          maxLength={CHAT_CONFIG.machineNameMaxLength}
          onChange={(event) => updateMachineName(event.currentTarget)}
          onCompositionEnd={(event) => updateMachineName(event.currentTarget)}
          onKeyDown={(event) => submitChatInputOnEnter(event, submitting ? undefined : onSubmit)}
          placeholder={CHAT_COPY.fields.machineNamePlaceholder}
          value={answers.name}
        />
        <small className="slsg-chat-character-count">
          {answers.name.length} / {CHAT_CONFIG.machineNameMaxLength}
        </small>
      </label>
    )
  }
  if (step === CHAT_STEPS.visibility) {
    return (
      <OptionButtons
        disabled={choicesDisabled}
        onSelect={(visibility) => selectChoice({ visibility })}
        options={VISIBILITY_OPTIONS}
        value={answers.visibility}
      />
    )
  }
  if (step === CHAT_STEPS.theme) {
    return (
      <div className="slsg-chat-theme-input">
        <div className="slsg-chat-theme-options">
          {SCENARIO_PROMPT_SUGGESTIONS.map((theme) => (
            <button
              className={`slsg-chat-option ${answers.theme === theme ? "is-selected" : ""}`}
              key={theme}
              onClick={() => onChange({ theme })}
              type="button"
            >
              {theme}
            </button>
          ))}
        </div>
        <ChatTextareaField
          inlineSubmit={inlineSubmit}
          label={CHAT_COPY.fields.scenarioPrompt}
          maxLength={CHAT_CONFIG.scenarioPromptMaxLength}
          onChange={(theme) => onChange({ theme })}
          onSubmit={onSubmit}
          placeholder={CHAT_COPY.fields.scenarioPromptPlaceholder}
          rows={5}
          submitting={submitting}
          value={answers.theme}
        />
      </div>
    )
  }
  if (step === CHAT_STEPS.difficulty) {
    return (
      <OptionButtons
        disabled={choicesDisabled}
        onSelect={(difficulty) => selectChoice({ difficulty })}
        options={DIFFICULTY_OPTIONS}
        value={answers.difficulty}
      />
    )
  }
  if (step === CHAT_STEPS.userFlagChoice) {
    return (
      <YesNoButtons
        disabled={choicesDisabled}
        onSelect={(needsUserFlag) => selectChoice({ needsUserFlag })}
        value={answers.needsUserFlag}
      />
    )
  }
  if (step === CHAT_STEPS.userFlagDetails) {
    return (
      <DetailInput
        label={CHAT_COPY.fields.userFlagDetails}
        inlineSubmit={inlineSubmit}
        onChange={(userFlagDetails) => onChange({ userFlagDetails })}
        onSubmit={onSubmit}
        placeholder={CHAT_COPY.fields.userFlagDetailsPlaceholder}
        submitting={submitting}
        value={answers.userFlagDetails}
      />
    )
  }
  if (step === CHAT_STEPS.systemFlagChoice) {
    return (
      <YesNoButtons
        disabled={choicesDisabled}
        onSelect={(needsSystemFlag) => selectChoice({ needsSystemFlag })}
        value={answers.needsSystemFlag}
      />
    )
  }
  return (
    <DetailInput
      label={CHAT_COPY.fields.systemFlagDetails}
      inlineSubmit={inlineSubmit}
      onChange={(systemFlagDetails) => onChange({ systemFlagDetails })}
      onSubmit={onSubmit}
      placeholder={CHAT_COPY.fields.systemFlagDetailsPlaceholder}
      submitting={submitting}
      value={answers.systemFlagDetails}
    />
  )
}

function DetailInput({
  inlineSubmit,
  label,
  onChange,
  onSubmit,
  placeholder,
  submitting,
  value,
}: {
  inlineSubmit: boolean
  label: string
  onChange: (value: string) => void
  onSubmit?: () => void
  placeholder: string
  submitting: boolean
  value: string
}) {
  return (
    <ChatTextareaField
      inlineSubmit={inlineSubmit}
      label={label}
      onChange={onChange}
      onSubmit={onSubmit}
      placeholder={placeholder}
      submitting={submitting}
      value={value}
    />
  )
}

function ChatTextareaField({
  inlineSubmit,
  label,
  maxLength,
  onChange,
  onSubmit,
  placeholder,
  rows,
  submitting,
  value,
}: {
  inlineSubmit: boolean
  label: string
  maxLength?: number
  onChange: (value: string) => void
  onSubmit?: () => void
  placeholder: string
  rows?: number
  submitting: boolean
  value: string
}) {
  const textareaId = useId()
  const updateValue = (textarea: HTMLTextAreaElement) => {
    onChange(maxLength === undefined ? textarea.value : limitChatInputValue(textarea, maxLength))
  }

  return (
    <div className="slsg-chat-field">
      <label htmlFor={textareaId}>{label}</label>
      <div className="slsg-input slsg-chat-textarea-shell">
        <textarea
          className="slsg-chat-textarea"
          id={textareaId}
          maxLength={maxLength}
          onChange={(event) => updateValue(event.currentTarget)}
          onCompositionEnd={(event) => {
            if (maxLength !== undefined) updateValue(event.currentTarget)
          }}
          onKeyDown={(event) => submitChatInputOnEnter(event, submitting ? undefined : onSubmit)}
          placeholder={placeholder}
          rows={rows}
          value={value}
        />
        {maxLength !== undefined || inlineSubmit ? (
          <div className="slsg-chat-textarea-footer">
            {maxLength !== undefined ? (
              <small className="slsg-chat-textarea-count">
                {value.length} / {maxLength}
              </small>
            ) : null}
            {inlineSubmit && onSubmit ? (
              <ChatSendButton disabled={submitting} onSubmit={onSubmit} submitting={submitting} />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function OptionButtons<T extends string>({
  disabled = false,
  onSelect,
  options,
  value,
}: {
  disabled?: boolean
  onSelect: (value: T) => void
  options: readonly T[]
  value: T | ""
}) {
  return (
    <div className="slsg-chat-option-grid">
      {options.map((option) => (
        <button
          className={`slsg-chat-option ${value === option ? "is-selected" : ""}`}
          disabled={disabled}
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
  disabled = false,
  onSelect,
  value,
}: {
  disabled?: boolean
  onSelect: (value: boolean) => void
  value: boolean | null
}) {
  return (
    <div className="slsg-chat-option-grid">
      <button
        className={`slsg-chat-option ${value === true ? "is-selected" : ""}`}
        disabled={disabled}
        onClick={() => onSelect(true)}
        type="button"
      >
        {CHAT_COPY.yesNo.yes}
      </button>
      <button
        className={`slsg-chat-option ${value === false ? "is-selected" : ""}`}
        disabled={disabled}
        onClick={() => onSelect(false)}
        type="button"
      >
        {CHAT_COPY.yesNo.no}
      </button>
    </div>
  )
}

export function MissingChatSession() {
  return (
    <section className="slsg-panel slsg-state-card">
      <div className="slsg-state-card-content">
        <span aria-hidden="true" className="slsg-state-card-icon">
          <AlertCircle size={25} strokeWidth={1.7} />
        </span>
        <h1>{CHAT_COPY.missingSession.title}</h1>
        <p>{CHAT_COPY.missingSession.message}</p>
        <Link className="slsg-state-card-action" href={CHAT_CONFIG.newChatPath}>
          {CHAT_COPY.missingSession.action}
          <ArrowRight aria-hidden="true" size={17} />
        </Link>
      </div>
    </section>
  )
}
