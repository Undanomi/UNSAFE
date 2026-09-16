import { type NextRequest, NextResponse } from "next/server"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { isProtectedRoute } from "@/lib/auth/routing"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getOrCreateUserDocumentService } from "@/lib/users/service"

const PROFILE_SETUP_PATH = "/profile/setup"

function deleteSessionCookie(response: NextResponse): NextResponse {
  response.cookies.delete(SESSION_COOKIE_NAME)
  return response
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)

  if (isProtectedRoute(pathname) && !user) {
    return deleteSessionCookie(NextResponse.redirect(new URL("/login", request.url)))
  }

  if (user && (pathname === "/login" || isProtectedRoute(pathname))) {
    const userDocument = await getOrCreateUserDocumentService(user)
    const profileCompleted = userDocument.profile_completed === true

    if (!profileCompleted && pathname !== PROFILE_SETUP_PATH) {
      return NextResponse.redirect(new URL(PROFILE_SETUP_PATH, request.url))
    }

    if (profileCompleted && pathname === PROFILE_SETUP_PATH) {
      return NextResponse.redirect(new URL("/machines", request.url))
    }

    if (pathname === "/login") {
      return NextResponse.redirect(new URL("/machines", request.url))
    }
  }

  const response = NextResponse.next()
  return sessionCookie && !user ? deleteSessionCookie(response) : response
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
}
