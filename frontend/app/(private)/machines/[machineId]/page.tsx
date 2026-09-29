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
  searchParams: Promise<{ from?: string; profileId?: string }>
}

export default async function MachineDetailPage({ params, searchParams }: MachineDetailPageProps) {
  const { machineId } = await params
  const { from, profileId } = await searchParams
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)

  if (!user) redirect("/login")

  const machine = await getMachineDetailService(user.uid, machineId)
  const cameFromProfile = from === "profile"
  const backHref =
    cameFromProfile && profileId && profileId !== user.uid
      ? `/users/${encodeURIComponent(profileId)}`
      : cameFromProfile
        ? "/profile"
        : "/machines"
  const backLabel = cameFromProfile ? "プロフィールに戻る" : "マシン一覧へ戻る"

  return (
    <AppShell artworkVariant="machines" layoutVariant="machine-detail">
      {machine ? (
        <MachineDetailView
          backHref={backHref}
          backLabel={backLabel}
          key={machine.id}
          machine={machine}
        />
      ) : (
        <MissingMachine backHref={backHref} backLabel={backLabel} />
      )}
    </AppShell>
  )
}
