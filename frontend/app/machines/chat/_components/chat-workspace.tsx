"use client"

import { ArrowRight, Bot, ChevronDown, ChevronUp, MessageSquareText, Pencil } from "lucide-react"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import {
  CHAT_CONFIG,
  CHAT_STEPS,
  type ChatAnswers,
  type ChatSession,
  chatCopy,
  chatPrompts,
  difficultyOptions,
  emptyChatAnswers,
  themeSuggestions,
  visibilityOptions,
} from "@/stores/chat"

type ChatWorkspaceProps = {
  session: ChatSession
}

function buildInitialAnswers(session: ChatSession): ChatAnswers {
  return { ...emptyChatAnswers, ...session.initialAnswers }
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
    ? chatCopy.errors.machineName
    : chatCopy.errors.answerRequired
}

function getChatPrompt(step: number, isBasicReady: boolean) {
  if (isBasicReady) return chatCopy.basicReadyPrompt
  return chatPrompts[step] ?? chatCopy.completePrompt
}

function buildChatSummary(answers: ChatAnswers) {
  const { labels } = chatCopy.summary
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
      prompt: chatPrompts[step],
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
  return value ? chatCopy.yesNo.yes : chatCopy.yesNo.no
}

export function ChatWorkspace({ session }: ChatWorkspaceProps) {
  const [answers, setAnswers] = useState<ChatAnswers>(() => buildInitialAnswers(session))
  const [step, setStep] = useState(session.initialStep)
  const [basicReady, setBasicReady] = useState(() => session.status === "基本設定完了")
  const [error, setError] = useState("")
  const [editingStep, setEditingStep] = useState<number | null>(null)
  const [editingError, setEditingError] = useState("")
  const [isSummaryOpen, setIsSummaryOpen] = useState(false)
  const conversationRef = useRef<HTMLDivElement>(null)

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

  function advance() {
    if (!isChatStepComplete(step, answers)) {
      setError(getChatValidationMessage(step))
      return
    }
    if (step === CHAT_STEPS.difficulty) {
      setBasicReady(true)
      return
    }
    const nextStep = getNextChatStep(step, answers)
    setStep(nextStep)
  }

  function continueDetails() {
    setBasicReady(false)
    setStep(CHAT_STEPS.userFlagChoice)
  }

  function handleMachineCreation() {
    return { answers, sessionId: session.id }
  }

  function startEditing(targetStep: number) {
    setEditingStep(targetStep)
    setEditingError("")
  }

  function completeEditing() {
    if (editingStep === null) return
    if (!isChatStepComplete(editingStep, answers)) {
      setEditingError(getChatValidationMessage(editingStep))
      return
    }
    setEditingStep(null)
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-92px)] max-w-5xl min-h-0 flex-col max-lg:h-[calc(100dvh-64px)]">
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl border border-[#e5e5e2] bg-white shadow-sm">
        <div className="border-b border-[#e5e5e2] px-7 py-5 max-sm:px-5">
          <div className="flex items-center justify-between gap-5 max-sm:items-start">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-[#20201e] text-white">
                <MessageSquareText aria-hidden="true" size={19} strokeWidth={2} />
              </span>
              <div>
                <p className="text-[0.78rem] font-bold text-[#61605b]">マシン作成アシスタント</p>
                <h1 className="mt-0.5 text-[clamp(1.2rem,2vw,1.5rem)] leading-[1.15] font-bold tracking-[-0.035em]">
                  {session.name}
                </h1>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3 max-sm:flex-col max-sm:items-end">
              <Link
                className="text-[0.78rem] font-bold text-[#61605b] hover:text-[#20201e]"
                href="/machines"
              >
                中止する
              </Link>
              <span className="rounded-full border border-[#d6d6d2] bg-[#f8f8f7] px-3 py-1.5 text-[0.75rem] font-extrabold text-[#61605b]">
                {chatCopy.progress} {progress} / {CHAT_STEPS.systemFlagDetails}
              </span>
            </div>
          </div>
          <div
            aria-label={`ステップ ${progress} / ${CHAT_STEPS.systemFlagDetails}`}
            aria-valuemax={CHAT_STEPS.systemFlagDetails}
            aria-valuemin={CHAT_CONFIG.progressMinimum}
            aria-valuenow={progress}
            className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#e5e5e2]"
            role="progressbar"
          >
            <span
              className="block h-full rounded-full bg-[#20201e] transition-[width]"
              style={{
                width: `${(progress / CHAT_STEPS.systemFlagDetails) * CHAT_CONFIG.progressPercentage}%`,
              }}
            />
          </div>
          <section className="mt-4">
            <button
              aria-expanded={isSummaryOpen}
              className="flex w-full items-center justify-between text-left text-[0.82rem] font-extrabold text-[#61605b] hover:text-[#20201e]"
              onClick={() => setIsSummaryOpen((open) => !open)}
              type="button"
            >
              <span>{chatCopy.summary.title}</span>
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
          <div className="grid gap-5">
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
            <AssistantMessage prompt={prompt} />
          </div>
        </div>

        <div className="border-t border-[#e5e5e2] bg-white px-7 py-5 max-sm:px-5">
          {!basicReady && !isFinalStep ? (
            <StepInput answers={answers} onChange={updateAnswers} step={step} />
          ) : null}
          {error ? <p className="mt-3 text-[0.86rem] font-bold text-[#b14334]">{error}</p> : null}
          {basicReady ? (
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
                onClick={handleMachineCreation}
                type="button"
              >
                {chatCopy.buttons.createBasic}
              </button>
              <button
                className="inline-flex min-h-[46px] items-center justify-center rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold text-[#20201e] shadow-sm transition hover:-translate-y-px"
                onClick={continueDetails}
                type="button"
              >
                {chatCopy.buttons.continueDetails}
              </button>
            </div>
          ) : isFinalStep ? (
            <button
              className="mt-5 inline-flex min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
              onClick={handleMachineCreation}
              type="button"
            >
              {chatCopy.buttons.createComplete}
            </button>
          ) : (
            <button
              className="mt-4 inline-flex min-h-10 items-center justify-center gap-1.5 rounded-xl border border-transparent bg-[#20201e] px-4 text-[0.82rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
              onClick={advance}
              type="button"
            >
              {step === CHAT_STEPS.difficulty ? (
                chatCopy.buttons.setBasic
              ) : (
                <>
                  {chatCopy.buttons.next}
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

function AssistantMessage({ prompt }: { prompt: { help: string; question: string } }) {
  return (
    <div className="flex items-start gap-3">
      <span
        aria-label={chatCopy.assistantLabel}
        className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#20201e] text-white"
        role="img"
      >
        <Bot aria-hidden="true" size={18} strokeWidth={2} />
      </span>
      <div className="min-w-0 rounded-2xl rounded-tl-sm border border-[#e5e5e2] bg-[#f8f8f7] px-4 py-3">
        <h2 className="text-[1rem] font-bold tracking-[-0.02em]">{prompt.question}</h2>
        {prompt.help ? (
          <p className="mt-1.5 text-[0.88rem] leading-[1.6] text-[#61605b]">{prompt.help}</p>
        ) : null}
      </div>
    </div>
  )
}

function UserMessage({ answer, onEdit }: { answer: string; onEdit: () => void }) {
  return (
    <div className="ml-auto flex max-w-[80%] flex-col items-end gap-1">
      <div className="w-full rounded-2xl rounded-tr-sm bg-[#20201e] px-4 py-3 text-white">
        <span className="text-[0.7rem] font-bold tracking-wide text-[#c5c4bd]">
          {chatCopy.userLabel}
        </span>
        <p className="mt-1 text-[0.9rem] leading-[1.55]">{answer}</p>
      </div>
      <button
        aria-label="この回答を編集"
        className="inline-flex size-7 items-center justify-center rounded-md text-[#61605b] hover:bg-[#f5f5f3] hover:text-[#20201e]"
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
    <div className="ml-auto grid w-full max-w-[80%] gap-4 rounded-2xl border border-[#d6d6d2] bg-white p-4 shadow-sm">
      <p className="text-[0.82rem] font-extrabold">回答を編集</p>
      <StepInput answers={answers} onChange={onChange} step={step} />
      {error ? <p className="text-[0.86rem] font-bold text-[#b14334]">{error}</p> : null}
      <button
        className="inline-flex w-fit min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
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
      <label className="grid gap-2 text-[0.86rem] font-extrabold">
        <span>{chatCopy.fields.machineName}</span>
        <input
          className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none placeholder:text-[#8a8984] focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
          maxLength={CHAT_CONFIG.machineNameMaxLength}
          onChange={(event) => onChange({ name: event.target.value })}
          placeholder={chatCopy.fields.machineNamePlaceholder}
          value={answers.name}
        />
        <small className="text-right text-[0.75rem] font-normal text-[#61605b]">
          {answers.name.length} / {CHAT_CONFIG.machineNameMaxLength}
        </small>
      </label>
    )
  }
  if (step === CHAT_STEPS.visibility) {
    return (
      <OptionButtons
        onSelect={(visibility) => onChange({ visibility })}
        options={visibilityOptions}
        value={answers.visibility}
      />
    )
  }
  if (step === CHAT_STEPS.theme) {
    return (
      <div className="grid gap-3">
        <div className="flex flex-wrap gap-2">
          {themeSuggestions.map((theme) => (
            <button
              className={`rounded-full border px-2.5 py-1 text-[0.78rem] font-bold transition ${
                answers.theme === theme
                  ? "border-[#20201e] bg-[#20201e] text-white"
                  : "border-[#d6d6d2] bg-white hover:border-[#20201e]"
              }`}
              key={theme}
              onClick={() => onChange({ theme })}
              type="button"
            >
              {theme}
            </button>
          ))}
        </div>
        <label className="grid gap-2 text-[0.86rem] font-extrabold">
          <span>{chatCopy.fields.freeInput}</span>
          <input
            className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none placeholder:text-[#8a8984] focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
            onChange={(event) => onChange({ theme: event.target.value })}
            placeholder={chatCopy.fields.themePlaceholder}
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
        options={difficultyOptions}
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
        label={chatCopy.fields.userFlagDetails}
        onChange={(userFlagDetails) => onChange({ userFlagDetails })}
        placeholder={chatCopy.fields.userFlagDetailsPlaceholder}
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
      label={chatCopy.fields.systemFlagDetails}
      onChange={(systemFlagDetails) => onChange({ systemFlagDetails })}
      placeholder={chatCopy.fields.systemFlagDetailsPlaceholder}
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
    <label className="grid gap-2 text-[0.86rem] font-extrabold">
      <span>{label}</span>
      <textarea
        className="min-h-28 w-full resize-y rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none placeholder:text-[#8a8984] focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
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
          className={`min-h-11 rounded-xl border px-3 text-left text-[0.82rem] font-extrabold transition ${
            value === option
              ? "border-[#20201e] bg-[#20201e] text-white"
              : "border-[#d6d6d2] bg-white hover:border-[#20201e]"
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
        className={`min-h-11 rounded-xl border px-3 text-left text-[0.82rem] font-extrabold transition ${
          value === true
            ? "border-[#20201e] bg-[#20201e] text-white"
            : "border-[#d6d6d2] bg-white hover:border-[#20201e]"
        }`}
        onClick={() => onSelect(true)}
        type="button"
      >
        {chatCopy.yesNo.yes}
      </button>
      <button
        className={`min-h-11 rounded-xl border px-3 text-left text-[0.82rem] font-extrabold transition ${
          value === false
            ? "border-[#20201e] bg-[#20201e] text-white"
            : "border-[#d6d6d2] bg-white hover:border-[#20201e]"
        }`}
        onClick={() => onSelect(false)}
        type="button"
      >
        {chatCopy.yesNo.no}
      </button>
    </div>
  )
}

function AnswerSummary({ answers }: { answers: ChatAnswers }) {
  return (
    <dl className="mt-4 grid grid-cols-2 gap-3 max-sm:grid-cols-1">
      {buildChatSummary(answers).map(([label, value]) => (
        <div className="rounded-xl bg-[#f8f8f7] p-3" key={label}>
          <dt className="text-[0.72rem] font-bold text-[#61605b]">{label}</dt>
          <dd className="mt-1 text-[0.88rem] font-bold">{value || chatCopy.summary.empty}</dd>
        </div>
      ))}
    </dl>
  )
}

export function MissingChatSession() {
  return (
    <section className="grid gap-4 rounded-3xl border border-[#e5e5e2] bg-white p-8 shadow-sm">
      <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
        {chatCopy.missingSession.title}
      </h1>
      <p className="leading-[1.65] text-[#61605b]">{chatCopy.missingSession.message}</p>
      <Link
        className="inline-flex w-fit min-h-[46px] items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
        href={CHAT_CONFIG.newChatPath}
      >
        {chatCopy.missingSession.action}
      </Link>
    </section>
  )
}
