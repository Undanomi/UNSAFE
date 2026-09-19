"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserDocumentService, updateUserProfileService } from "@/lib/users/service"

const MAX_NAME_LENGTH = 30
const MAX_BIO_LENGTH = 500

export type UpdateProfileActionResult =
  | { success: true; profile: { name: string; bio: string; iconUrl: string } }
  | { success: false; message: string }

export type CompleteProfileActionResult = { success: true } | { success: false; message: string }

async function getAuthenticatedUser() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  return verifySessionCookieService(sessionCookie, { checkRevoked: true })
}

function readProfileFields(formData: FormData) {
  const rawName = formData.get("name")
  const rawBio = formData.get("bio")

  return {
    name: typeof rawName === "string" ? rawName.trim() : "",
    bio: typeof rawBio === "string" ? rawBio.trim() : "",
  }
}

function readIconMode(formData: FormData): "google" | "initial" | null {
  const iconMode = formData.get("icon_mode")
  return iconMode === "google" || iconMode === "initial" ? iconMode : null
}

function validateProfileFields(name: string, bio: string): string | null {
  if (!name || name.length > MAX_NAME_LENGTH) {
    return `ユーザー名は1〜${MAX_NAME_LENGTH}文字で入力してください。`
  }

  if (bio.length > MAX_BIO_LENGTH) {
    return `自己紹介は${MAX_BIO_LENGTH}文字以内で入力してください。`
  }

  return null
}

export async function updateProfileAction(formData: FormData): Promise<UpdateProfileActionResult> {
  const user = await getAuthenticatedUser()

  if (!user) {
    return {
      success: false,
      message: "ログイン情報を確認できませんでした。再度ログインしてください。",
    }
  }

  const { name, bio } = readProfileFields(formData)
  const iconMode = readIconMode(formData)
  const validationMessage = validateProfileFields(name, bio)
  if (validationMessage) return { success: false, message: validationMessage }
  if (!iconMode) return { success: false, message: "アイコンの表示方法を選択してください。" }

  try {
    const currentProfile = await getUserDocumentService(user.uid)
    if (!currentProfile) throw new Error("Authenticated user document was not found.")

    const iconUrl = iconMode === "google" ? user.picture || currentProfile.icon_url : ""
    await updateUserProfileService(user.uid, { name, bio, icon_url: iconUrl })
    revalidatePath("/profile")
    return { success: true, profile: { name, bio, iconUrl } }
  } catch (error) {
    console.error("Failed to update user profile.", error)
    return {
      success: false,
      message: "プロフィールを保存できませんでした。もう一度お試しください。",
    }
  }
}

export async function completeProfileAction(
  formData: FormData,
): Promise<CompleteProfileActionResult> {
  const user = await getAuthenticatedUser()

  if (!user) {
    return {
      success: false,
      message: "ログイン情報を確認できませんでした。再度ログインしてください。",
    }
  }

  const { name } = readProfileFields(formData)
  const iconMode = readIconMode(formData)
  const validationMessage = validateProfileFields(name, "")
  if (validationMessage) return { success: false, message: validationMessage }
  if (!iconMode) return { success: false, message: "アイコンの表示方法を選択してください。" }

  try {
    const currentProfile = await getUserDocumentService(user.uid)
    if (!currentProfile) throw new Error("Authenticated user document was not found.")

    await updateUserProfileService(user.uid, {
      icon_url: iconMode === "google" ? user.picture || currentProfile.icon_url : "",
      name,
      profile_completed: true,
    })
    revalidatePath("/", "layout")
    return { success: true }
  } catch (error) {
    console.error("Failed to complete user profile.", error)
    return {
      success: false,
      message: "プロフィールを登録できませんでした。もう一度お試しください。",
    }
  }
}
