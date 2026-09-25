"use server"

import { cookies } from "next/headers"
import {
  cancelAiSessionService,
  createAiSessionService,
  saveMachineInformationService,
  startMachineBuildService,
} from "@/lib/ai/service"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import {
  createChatSessionService,
  createMachineDocumentService,
  saveChatProgressService,
  setChatCreationCancelledService,
  setChatCreationFailureService,
  setChatCreationReadyService,
  setChatCreationStatusService,
} from "@/lib/chat/service"
import {
  CHAT_CONFIG,
  CHAT_STEPS,
  type ChatAnswers,
  type ChatCreationFailure,
  DIFFICULTY_OPTIONS,
  VISIBILITY_OPTIONS,
} from "@/stores/chat"

const GENERIC_ERROR_MESSAGE = "処理に失敗しました。しばらくしてからもう一度お試しください。"
const SESSION_ERROR_MESSAGE = "このチャットを操作する権限がないか、チャットが見つかりません。"

type ChatActionSuccess = { success: true; sessionId: string }
type ChatActionFailure = { success: false; message: string }
export type ChatActionResult = ChatActionSuccess | ChatActionFailure

type SaveChatProgressInput = {
  sessionId: string | null
  answers: ChatAnswers
  currentStep: number
  basicReady: boolean
}

async function getAuthenticatedUser() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  return verifySessionCookieService(sessionCookie)
}

function isStringWithin(value: unknown, minimum: number, maximum: number): value is string {
  return typeof value === "string" && value.trim().length >= minimum && value.length <= maximum
}

function parseAnswers(value: ChatAnswers): ChatAnswers | null {
  if (!value || typeof value !== "object") return null
  if (!isStringWithin(value.name, 1, CHAT_CONFIG.machineNameMaxLength)) return null
  if (value.visibility !== "" && !VISIBILITY_OPTIONS.includes(value.visibility)) return null
  if (typeof value.theme !== "string" || value.theme.length > 500) return null
  if (value.difficulty !== "" && !DIFFICULTY_OPTIONS.includes(value.difficulty)) return null
  if (value.needsUserFlag !== null && typeof value.needsUserFlag !== "boolean") return null
  if (typeof value.userFlagDetails !== "string" || value.userFlagDetails.length > 4000) return null
  if (value.needsSystemFlag !== null && typeof value.needsSystemFlag !== "boolean") return null
  if (typeof value.systemFlagDetails !== "string" || value.systemFlagDetails.length > 4000)
    return null

  return {
    name: value.name.trim(),
    visibility: value.visibility,
    theme: value.theme.trim(),
    difficulty: value.difficulty,
    needsUserFlag: value.needsUserFlag,
    userFlagDetails: value.userFlagDetails.trim(),
    needsSystemFlag: value.needsSystemFlag,
    systemFlagDetails: value.systemFlagDetails.trim(),
  }
}

function isValidProgress(answers: ChatAnswers, currentStep: number, basicReady: boolean) {
  if (!Number.isInteger(currentStep) || currentStep < CHAT_STEPS.visibility) return false
  if (currentStep > CHAT_STEPS.complete) return false
  if (currentStep >= CHAT_STEPS.theme && !answers.visibility) return false
  if (currentStep >= CHAT_STEPS.difficulty && !answers.theme) return false
  if ((basicReady || currentStep >= CHAT_STEPS.userFlagChoice) && !answers.difficulty) return false
  if (currentStep >= CHAT_STEPS.userFlagDetails && answers.needsUserFlag === null) return false
  if (
    answers.needsUserFlag === true &&
    currentStep >= CHAT_STEPS.systemFlagChoice &&
    !answers.userFlagDetails
  )
    return false
  if (currentStep >= CHAT_STEPS.systemFlagDetails && answers.needsSystemFlag === null) return false
  if (
    answers.needsSystemFlag === true &&
    currentStep === CHAT_STEPS.complete &&
    !answers.systemFlagDetails
  )
    return false
  return true
}

function hasRequiredMachineInformation(answers: ChatAnswers) {
  if (!answers.visibility || !answers.theme || !answers.difficulty) return false
  const hasStartedDetailedSettings =
    answers.needsUserFlag !== null || answers.needsSystemFlag !== null
  if (
    hasStartedDetailedSettings &&
    (answers.needsUserFlag === null || answers.needsSystemFlag === null)
  )
    return false
  if (answers.needsUserFlag === true && !answers.userFlagDetails) return false
  if (answers.needsSystemFlag === true && !answers.systemFlagDetails) return false
  return true
}

export async function saveChatProgressAction(
  input: SaveChatProgressInput,
): Promise<ChatActionResult> {
  const user = await getAuthenticatedUser()
  if (!user) return { success: false, message: "ログインし直してください。" }

  const answers = parseAnswers(input.answers)
  if (!answers || !isValidProgress(answers, input.currentStep, input.basicReady)) {
    return { success: false, message: "入力内容を確認してください。" }
  }

  try {
    if (!input.sessionId) {
      const aiSessionId = await createAiSessionService(user.uid)
      await createChatSessionService(
        user.uid,
        aiSessionId,
        answers,
        input.currentStep,
        input.basicReady,
      )
      return { success: true, sessionId: aiSessionId }
    }

    const session = await saveChatProgressService(
      user.uid,
      input.sessionId,
      answers,
      input.currentStep,
      input.basicReady,
    )
    return session
      ? { success: true, sessionId: session.id }
      : { success: false, message: SESSION_ERROR_MESSAGE }
  } catch (error) {
    console.error("Failed to save chat progress.", error)
    return { success: false, message: GENERIC_ERROR_MESSAGE }
  }
}

export async function prepareMachineCreationAction(
  sessionId: string,
  rawAnswers: ChatAnswers,
): Promise<ChatActionResult> {
  const user = await getAuthenticatedUser()
  if (!user) return { success: false, message: "ログインし直してください。" }

  const answers = parseAnswers(rawAnswers)
  if (!answers || !hasRequiredMachineInformation(answers)) {
    return { success: false, message: "マシンの設定に未入力の項目があります。" }
  }

  try {
    const isBasicOnly = answers.needsUserFlag === null && answers.needsSystemFlag === null
    const saved = await saveChatProgressService(
      user.uid,
      sessionId,
      answers,
      isBasicOnly ? CHAT_STEPS.difficulty : CHAT_STEPS.complete,
      isBasicOnly,
    )
    if (!saved) return { success: false, message: SESSION_ERROR_MESSAGE }

    await saveMachineInformationService(user.uid, sessionId, answers)
    await setChatCreationStatusService(user.uid, sessionId, "generating_scenario")
    return { success: true, sessionId }
  } catch (error) {
    console.error("Failed to prepare machine creation.", error)
    return { success: false, message: GENERIC_ERROR_MESSAGE }
  }
}

export async function startMachineBuildAction(
  sessionId: string,
  scenarioId: string,
): Promise<ChatActionResult & { machineId?: string }> {
  const user = await getAuthenticatedUser()
  if (!user) return { success: false, message: "ログインし直してください。" }
  if (!scenarioId || scenarioId.length > 200) {
    return { success: false, message: "AIから返されたシナリオを確認できませんでした。" }
  }

  try {
    const started = await startMachineBuildService(user.uid, sessionId, scenarioId)
    const machineId = await createMachineDocumentService(user.uid, sessionId, {
      userFlag: started.user_flag,
      systemFlag: started.system_flag,
    })
    return machineId
      ? { success: true, sessionId, machineId }
      : { success: false, message: SESSION_ERROR_MESSAGE }
  } catch (error) {
    console.error("Failed to start machine build.", error)
    return { success: false, message: GENERIC_ERROR_MESSAGE }
  }
}

export async function markMachineCreationFailedAction(
  sessionId: string,
  failure: ChatCreationFailure,
): Promise<void> {
  const user = await getAuthenticatedUser()
  if (!user) return
  const normalized: ChatCreationFailure = {
    kind:
      failure.kind === "settings"
        ? "settings"
        : failure.kind === "ai_safety_refusal"
          ? "ai_safety_refusal"
          : "system",
    summary: failure.summary.trim().slice(0, 4000),
    suggestions: failure.suggestions
      .filter((suggestion) => typeof suggestion === "string" && suggestion.trim())
      .slice(0, 5)
      .map((suggestion) => suggestion.trim().slice(0, 4000)),
  }
  await setChatCreationFailureService(user.uid, sessionId, normalized)
}

export async function cancelMachineCreationAction(sessionId: string): Promise<ChatActionResult> {
  const user = await getAuthenticatedUser()
  if (!user) return { success: false, message: "ログインし直してください。" }

  try {
    await cancelAiSessionService(user.uid, sessionId)
    const updated = await setChatCreationCancelledService(user.uid, sessionId)
    return updated
      ? { success: true, sessionId }
      : { success: false, message: SESSION_ERROR_MESSAGE }
  } catch (error) {
    console.error("Failed to cancel machine creation.", error)
    return { success: false, message: "マシン作成を中止できませんでした。" }
  }
}

export async function markMachineCreationReadyAction(sessionId: string): Promise<ChatActionResult> {
  const user = await getAuthenticatedUser()
  if (!user) return { success: false, message: "ログインし直してください。" }

  const updated = await setChatCreationReadyService(user.uid, sessionId)
  return updated ? { success: true, sessionId } : { success: false, message: SESSION_ERROR_MESSAGE }
}
