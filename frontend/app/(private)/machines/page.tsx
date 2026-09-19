import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { Suspense } from "react"
import {
  MachineList,
  MachineListLoading,
  MachineListResults,
} from "@/app/(private)/machines/machine-list"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import {
  type MachineListQuery,
  machineListHref,
  parseMachineListQuery,
} from "@/lib/machines/list-query"
import { getMachineListService } from "@/lib/machines/list-service"

async function MachineResults({ uid, query }: { uid: string; query: MachineListQuery }) {
  const result = await getMachineListService(uid, query)
  if (query.page !== result.page) redirect(machineListHref(query, result.page))
  return <MachineListResults result={result} query={query} />
}

export default async function MachinesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)
  if (!user) redirect("/login")
  const query = parseMachineListQuery(await searchParams)
  return (
    <AppShell>
      <MachineList query={query}>
        <Suspense key={`results:${machineListHref(query)}`} fallback={<MachineListLoading />}>
          <MachineResults uid={user.uid} query={query} />
        </Suspense>
      </MachineList>
    </AppShell>
  )
}
