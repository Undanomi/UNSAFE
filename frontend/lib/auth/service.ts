import "server-only"

import type { DecodedIdToken } from "firebase-admin/auth"
import { RECENT_SIGN_IN_SECONDS, SESSION_DURATION_SECONDS } from "@/lib/auth/constants"
import { getFirebaseAdminAuth } from "@/lib/firebase/admin"
import { getOrCreateUserDocumentService } from "@/lib/users/service"

const MAX_FUTURE_AUTHENTICATION_SECONDS = 60

export type AuthenticatedUser = {
  uid: string
  name: string
  picture: string | null
}

function isRecentAuthentication(authTime: number): boolean {
  const authenticatedSecondsAgo = Math.floor(Date.now() / 1000) - authTime

  return (
    Number.isFinite(authenticatedSecondsAgo) &&
    authenticatedSecondsAgo >= -MAX_FUTURE_AUTHENTICATION_SECONDS &&
    authenticatedSecondsAgo <= RECENT_SIGN_IN_SECONDS
  )
}

function toAuthenticatedUser(token: DecodedIdToken): AuthenticatedUser {
  return {
    uid: token.uid,
    name: typeof token.name === "string" && token.name.trim() ? token.name : "ユーザー",
    picture: typeof token.picture === "string" && token.picture ? token.picture : null,
  }
}

export async function createSessionService(
  idToken: string,
): Promise<{ sessionCookie: string; profileCompleted: boolean }> {
  const auth = getFirebaseAdminAuth()
  const decodedToken = await auth.verifyIdToken(idToken, true)

  if (!isRecentAuthentication(decodedToken.auth_time)) {
    throw new Error("The Firebase ID token is not recently authenticated.")
  }

  const sessionCookie = await auth.createSessionCookie(idToken, {
    expiresIn: SESSION_DURATION_SECONDS * 1000,
  })

  const userDocument = await getOrCreateUserDocumentService(decodedToken)

  return {
    sessionCookie,
    profileCompleted: userDocument.profile_completed === true,
  }
}

export async function verifySessionCookieService(
  sessionCookie: string,
  options: { checkRevoked?: boolean } = {},
): Promise<AuthenticatedUser | null> {
  if (!sessionCookie) return null

  try {
    const token = await getFirebaseAdminAuth().verifySessionCookie(
      sessionCookie,
      options.checkRevoked ?? false,
    )
    return toAuthenticatedUser(token)
  } catch {
    return null
  }
}
