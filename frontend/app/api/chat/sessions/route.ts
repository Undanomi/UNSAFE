import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { listChatSessionsService } from "@/lib/chat/service"

export async function GET() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return NextResponse.json({ message: "Unauthorized" }, { status: 401 })

  try {
    const sessions = await listChatSessionsService(user.uid)
    return NextResponse.json({ sessions }, { headers: { "Cache-Control": "private, no-store" } })
  } catch (error) {
    console.error("Failed to list chat sessions.", error)
    return NextResponse.json({ message: "Failed to load chat sessions" }, { status: 500 })
  }
}
