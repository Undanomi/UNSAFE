import { cookies } from "next/headers"
import {
  MachineDetailView,
  MissingMachine,
} from "@/app/(private)/machines/[machineId]/machine-detail"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getMachineDetailService } from "@/lib/machines/service"
import { MACHINE_DETAILS } from "@/stores/machine-detail"

type MachineDetailPageProps = {
  params: Promise<{ machineId: string }>
}

export default async function MachineDetailPage({ params }: MachineDetailPageProps) {
  const { machineId } = await params
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  const machine =
    MACHINE_DETAILS[machineId] ?? (user ? await getMachineDetailService(user.uid, machineId) : null)

  return (
    <AppShell>{machine ? <MachineDetailView machine={machine} /> : <MissingMachine />}</AppShell>
  )
}
