import { type NextRequest, NextResponse } from "next/server"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { isProtectedRoute } from "@/lib/auth/routing"
import { verifySessionCookieService } from "@/lib/auth/service"

function deleteSessionCookie(response: NextResponse): NextResponse {
  response.cookies.delete(SESSION_COOKIE_NAME)
  return response
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const sessionCookie = request.cookies.get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)

  if (pathname === "/login" && user) {
    return NextResponse.redirect(new URL("/machines", request.url))
  }

  if (isProtectedRoute(pathname) && !user) {
    return deleteSessionCookie(NextResponse.redirect(new URL("/login", request.url)))
  }

  const response = NextResponse.next()
  return sessionCookie && !user ? deleteSessionCookie(response) : response
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
}
