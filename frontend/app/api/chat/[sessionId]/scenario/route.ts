import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { openScenarioStreamService } from "@/lib/ai/service"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getChatSessionService } from "@/lib/chat/service"

type ScenarioRouteContext = {
  params: Promise<{ sessionId: string }>
}

export async function GET(_request: Request, { params }: ScenarioRouteContext) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return NextResponse.json({ message: "Unauthorized" }, { status: 401 })

  const { sessionId } = await params
  const session = await getChatSessionService(user.uid, sessionId)
  if (!session) return NextResponse.json({ message: "Not found" }, { status: 404 })

  try {
    const upstream = await openScenarioStreamService(user.uid, sessionId)
    if (!upstream.ok || !upstream.body) {
      console.error("AI server rejected the scenario stream request.", upstream.status)
      return new Response(null, { status: upstream.status || 502 })
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    })
  } catch (error) {
    console.error("Failed to open scenario stream.", error)
    return new Response(null, { status: 502 })
  }
}
