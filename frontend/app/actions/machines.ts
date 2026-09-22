"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import {
  generateMachineGuidanceService,
  retryMachineBuildService,
  verifyMachineFlagService,
} from "@/lib/machines/service"
import type { MachineBuildState, MachineGuidance } from "@/stores/machine-detail"

export type GenerateMachineGuidanceResult =
  | { success: true; guidance: MachineGuidance }
  | { success: false; message: string }

export async function generateMachineGuidanceAction(
  machineId: string,
  regenerate = false,
): Promise<GenerateMachineGuidanceResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return { success: false, message: "ログインし直してください。" }
  if (!machineId || machineId.length > 200 || typeof regenerate !== "boolean") {
    return { success: false, message: "マシンを確認できませんでした。" }
  }

  try {
    const guidance = await generateMachineGuidanceService(user.uid, machineId, regenerate)
    if (!guidance) {
      return { success: false, message: "このマシンでは誘導問題を作成できません。" }
    }
    revalidatePath(`/machines/${machineId}`)
    return { success: true, guidance }
  } catch (error) {
    console.error("Failed to generate machine guidance.", error)
    return {
      success: false,
      message: "誘導問題を作成できませんでした。しばらくしてからもう一度お試しください。",
    }
  }
}

export type RetryMachineBuildResult =
  | { success: true; state: MachineBuildState }
  | { success: false; message: string }

export async function retryMachineBuildAction(machineId: string): Promise<RetryMachineBuildResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return { success: false, message: "ログインし直してください。" }
  if (!machineId || machineId.length > 200) {
    return { success: false, message: "マシンを確認できませんでした。" }
  }

  try {
    const state = await retryMachineBuildService(user.uid, machineId)
    return state
      ? { success: true, state }
      : { success: false, message: "このマシンを再ビルドする権限がありません。" }
  } catch (error) {
    console.error("Failed to retry machine build.", error)
    return {
      success: false,
      message: "再ビルドを開始できませんでした。しばらくしてからもう一度お試しください。",
    }
  }
}

export type VerifyMachineFlagResult = { success: true; correct: boolean } | { success: false }

export async function verifyMachineFlagAction(
  machineId: string,
  kind: "user" | "system",
  answer: string,
): Promise<VerifyMachineFlagResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return { success: false }
  if (
    !machineId ||
    machineId.length > 200 ||
    !["user", "system"].includes(kind) ||
    !answer.trim() ||
    answer.length > 200
  ) {
    return { success: false }
  }

  try {
    const correct = await verifyMachineFlagService(user.uid, machineId, kind, answer)
    if (correct) revalidatePath("/machines")
    return correct === null ? { success: false } : { success: true, correct }
  } catch (error) {
    console.error("Failed to verify machine flag.", error)
    return { success: false }
  }
}
