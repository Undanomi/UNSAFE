import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ProfileEditor } from "@/app/(private)/profile/profile-editor"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserProfileService } from "@/lib/users/service"

type UserPageProps = {
  params: Promise<{ userId: string }>
}

export default async function UserPage({ params }: UserPageProps) {
  const { userId } = await params

  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)

  if (!authenticatedUser) redirect("/login")

  const profile = await getUserProfileService(authenticatedUser.uid, userId)
  return (
    <AppShell artworkVariant="machines" layoutVariant="profile">
      {profile ? (
        <ProfileEditor canEdit={false} key={profile.id} profile={profile} />
      ) : (
        <section className="grid gap-3 rounded-3xl border border-[#e5e5e2] bg-white p-8 shadow-sm">
          <h1 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]">
            このユーザーは見つかりませんでした。
          </h1>
          <p className="leading-[1.65] text-[#61605b]">
            マシン一覧から別の作成者を選択してください。
          </p>
        </section>
      )}
    </AppShell>
  )
}
