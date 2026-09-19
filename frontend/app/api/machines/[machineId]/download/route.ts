import { cookies } from "next/headers"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { openMachineDownloadService } from "@/lib/machines/service"

const FORWARDED_HEADERS = [
  "accept-ranges",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
  "etag",
  "last-modified",
] as const

type MachineDownloadRouteContext = {
  params: Promise<{ machineId: string }>
}

export async function GET(request: Request, { params }: MachineDownloadRouteContext) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return new Response(null, { status: 401 })

  const { machineId } = await params
  try {
    const upstream = await openMachineDownloadService(
      user.uid,
      machineId,
      request.headers.get("range"),
      request.headers.get("if-range"),
    )
    if (!upstream) return new Response(null, { status: 404 })

    const headers = new Headers({
      "Cache-Control": "private, no-store",
      "Referrer-Policy": "no-referrer",
    })
    for (const name of FORWARDED_HEADERS) {
      const value = upstream.headers.get(name)
      if (value) headers.set(name, value)
    }

    if (!upstream.ok) {
      await upstream.body?.cancel()
      return new Response(null, { status: upstream.status, headers })
    }
    return new Response(upstream.body, { status: upstream.status, headers })
  } catch (error) {
    console.error("Failed to download machine artifact.", error)
    return new Response(null, { status: 502 })
  }
}
