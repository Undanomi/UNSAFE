"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { SESSION_COOKIE_NAME, SESSION_DURATION_SECONDS } from "@/lib/auth/constants"
import { createSessionService } from "@/lib/auth/service"

export type AuthActionResult = { success: true } | { success: false; message: string }

const AUTHENTICATION_ERROR_MESSAGE = "Google ログインに失敗しました。もう一度お試しください。"

export async function createSessionAction(idToken: string): Promise<AuthActionResult> {
  if (!idToken || idToken.length > 16_384) {
    return { success: false, message: AUTHENTICATION_ERROR_MESSAGE }
  }

  try {
    const sessionCookie = await createSessionService(idToken)

    ;(await cookies()).set(SESSION_COOKIE_NAME, sessionCookie, {
      httpOnly: true,
      maxAge: SESSION_DURATION_SECONDS,
      path: "/",
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to create Firebase session.", error)
    return { success: false, message: AUTHENTICATION_ERROR_MESSAGE }
  }
}

export async function logoutAction(): Promise<never> {
  ;(await cookies()).delete(SESSION_COOKIE_NAME)
  redirect("/login")
}
