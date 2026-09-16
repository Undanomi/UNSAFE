"use server"

import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { retryMachineBuildService } from "@/lib/machines/service"
import type { MachineBuildState } from "@/stores/machine-detail"

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
