import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import {
  MachineDetailView,
  MissingMachine,
} from "@/app/(private)/machines/[machineId]/machine-detail"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getMachineDetailService } from "@/lib/machines/service"

type MachineDetailPageProps = {
  params: Promise<{ machineId: string }>
}

export default async function MachineDetailPage({ params }: MachineDetailPageProps) {
  const { machineId } = await params
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)

  if (!user) redirect("/login")

  const machine = await getMachineDetailService(user.uid, machineId)

  return (
    <AppShell>{machine ? <MachineDetailView machine={machine} /> : <MissingMachine />}</AppShell>
  )
}
