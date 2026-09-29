"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import {
  generateMachineGuidanceService,
  retryMachineBuildService,
  updateMachineDetailsService,
  verifyMachineFlagService,
} from "@/lib/machines/service"
import type { MachineBuildState, MachineGuidance } from "@/types/machine-detail"
import type { MachineRecord } from "@/types/postgres"

export type UpdateMachineDetailsResult =
  | {
      success: true
      machine: { name: string; level: MachineRecord["level"]; published: boolean }
    }
  | { success: false; message: string }

export async function updateMachineDetailsAction(
  machineId: string,
  formData: FormData,
): Promise<UpdateMachineDetailsResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return { success: false, message: "ログインし直してください。" }
  if (typeof machineId !== "string" || !machineId || machineId.length > 200) {
    return { success: false, message: "マシンを確認できませんでした。" }
  }

  const rawName = formData.get("name")
  const rawLevel = formData.get("level")
  const rawPublished = formData.get("published")
  if (typeof rawName !== "string") {
    return { success: false, message: "マシン名を入力してください。" }
  }
  const name = rawName.trim()
  if (!name || name.length > 40) {
    return { success: false, message: "マシン名は1〜40文字で入力してください。" }
  }
  if (
    rawLevel !== "very_easy" &&
    rawLevel !== "easy" &&
    rawLevel !== "medium" &&
    rawLevel !== "hard"
  ) {
    return { success: false, message: "難易度を選択してください。" }
  }
  if (rawPublished !== "true" && rawPublished !== "false") {
    return { success: false, message: "公開設定を選択してください。" }
  }

  try {
    const updated = await updateMachineDetailsService(user.uid, machineId, {
      name,
      level: rawLevel,
      published: rawPublished === "true",
    })
    if (!updated) {
      return {
        success: false,
        message: "このマシンを編集する権限がないか、ビルドが完了していません。",
      }
    }
    revalidatePath(`/machines/${machineId}`)
    revalidatePath("/machines")
    revalidatePath("/profile")
    revalidatePath(`/users/${user.uid}`)
    revalidatePath("/machines/chat")
    if (updated.chatSessionId) revalidatePath(`/machines/chat/${updated.chatSessionId}`)
    return {
      success: true,
      machine: { name: updated.name, level: updated.level, published: updated.published },
    }
  } catch (error) {
    console.error("Failed to update machine details.", error)
    return { success: false, message: "マシン情報を保存できませんでした。もう一度お試しください。" }
  }
}

export type UpdateMachineDetailsResult =
  | {
      success: true
      machine: { name: string; level: "easy" | "medium" | "hard"; published: boolean }
    }
  | { success: false; message: string }

export async function updateMachineDetailsAction(
  machineId: string,
  formData: FormData,
): Promise<UpdateMachineDetailsResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return { success: false, message: "ログインし直してください。" }
  if (typeof machineId !== "string" || !machineId || machineId.length > 200) {
    return { success: false, message: "マシンを確認できませんでした。" }
  }

  const rawName = formData.get("name")
  const rawLevel = formData.get("level")
  const rawPublished = formData.get("published")
  if (typeof rawName !== "string") {
    return { success: false, message: "マシン名を入力してください。" }
  }
  const name = rawName.trim()
  if (!name || name.length > 40) {
    return { success: false, message: "マシン名は1〜40文字で入力してください。" }
  }
  if (rawLevel !== "easy" && rawLevel !== "medium" && rawLevel !== "hard") {
    return { success: false, message: "難易度を選択してください。" }
  }
  if (rawPublished !== "true" && rawPublished !== "false") {
    return { success: false, message: "公開設定を選択してください。" }
  }

  try {
    const updated = await updateMachineDetailsService(user.uid, machineId, {
      name,
      level: rawLevel,
      published: rawPublished === "true",
    })
    if (!updated) {
      return {
        success: false,
        message: "このマシンを編集する権限がないか、ビルドが完了していません。",
      }
    }
    revalidatePath(`/machines/${machineId}`)
    revalidatePath("/machines")
    revalidatePath("/profile")
    revalidatePath(`/users/${user.uid}`)
    revalidatePath("/machines/chat")
    if (updated.chatSessionId) revalidatePath(`/machines/chat/${updated.chatSessionId}`)
    return {
      success: true,
      machine: { name: updated.name, level: updated.level, published: updated.published },
    }
  } catch (error) {
    console.error("Failed to update machine details.", error)
    return { success: false, message: "マシン情報を保存できませんでした。もう一度お試しください。" }
  }
}

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

    if (correct) {
      revalidatePath("/machines")
      revalidatePath("/profile")
      revalidatePath(`/users/${user.uid}`)
    }

    return correct === null ? { success: false } : { success: true, correct }
  } catch (error) {
    console.error("Failed to verify machine flag.", error)
    return { success: false }
  }
}
