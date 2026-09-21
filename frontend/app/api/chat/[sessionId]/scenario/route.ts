import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { openScenarioStreamService } from "@/lib/ai/service"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getChatSessionService } from "@/lib/chat/service"

type ScenarioRouteContext = {
  params: Promise<{ sessionId: string }>
}

function proxyScenarioStream(upstream: ReadableStream<Uint8Array>) {
  const reader = upstream.getReader()
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read()
        if (done) {
          controller.close()
          return
        }
        controller.enqueue(value)
      } catch {
        // Close cleanly so the browser can reconnect without Next.js reporting a pipe failure.
        controller.close()
      }
    },
    cancel(reason) {
      return reader.cancel(reason)
    },
  })
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

    return new Response(proxyScenarioStream(upstream.body), {
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
