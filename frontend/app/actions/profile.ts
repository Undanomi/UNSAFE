"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { updateUserProfileService } from "@/lib/users/service"

const MAX_NAME_LENGTH = 30
const MAX_BIO_LENGTH = 500

export type UpdateProfileActionResult =
  | { success: true; profile: { name: string; bio: string } }
  | { success: false; message: string }

export async function updateProfileAction(input: {
  name?: unknown
  bio?: unknown
}): Promise<UpdateProfileActionResult> {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie, { checkRevoked: true })

  if (!user) {
    return {
      success: false,
      message: "ログイン情報を確認できませんでした。再度ログインしてください。",
    }
  }

  const name = typeof input?.name === "string" ? input.name.trim() : ""
  const bio = typeof input?.bio === "string" ? input.bio.trim() : ""

  if (!name || name.length > MAX_NAME_LENGTH) {
    return { success: false, message: `ユーザー名は1〜${MAX_NAME_LENGTH}文字で入力してください。` }
  }

  if (bio.length > MAX_BIO_LENGTH) {
    return { success: false, message: `自己紹介は${MAX_BIO_LENGTH}文字以内で入力してください。` }
  }

  try {
    await updateUserProfileService(user.uid, { name, bio })
    revalidatePath("/profile")
    return { success: true, profile: { name, bio } }
  } catch (error) {
    console.error("Failed to update user profile.", error)
    return {
      success: false,
      message: "プロフィールを保存できませんでした。もう一度お試しください。",
    }
  }
}
