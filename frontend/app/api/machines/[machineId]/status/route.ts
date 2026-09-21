import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getMachineBuildStateService } from "@/lib/machines/service"

type MachineStatusRouteContext = {
  params: Promise<{ machineId: string }>
}

export async function GET(_request: Request, { params }: MachineStatusRouteContext) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) return NextResponse.json({ message: "Unauthorized" }, { status: 401 })

  const { machineId } = await params
  try {
    const state = await getMachineBuildStateService(user.uid, machineId)
    return state
      ? NextResponse.json(state, { headers: { "Cache-Control": "private, no-store" } })
      : NextResponse.json({ message: "Not found" }, { status: 404 })
  } catch (error) {
    console.error("Failed to load machine status.", error)
    return NextResponse.json({ message: "Failed to load machine status" }, { status: 502 })
  }
}
