import { UserRoundX } from "lucide-react"
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
  if (userId === authenticatedUser.uid) redirect("/profile")

  const profile = await getUserProfileService(authenticatedUser.uid, userId)
  return (
    <AppShell artworkVariant="machines" layoutVariant="profile">
      {profile ? (
        <ProfileEditor canEdit={false} key={profile.id} profile={profile} />
      ) : (
        <section className="slsg-panel slsg-state-card">
          <div className="slsg-state-card-content">
            <span aria-hidden="true" className="slsg-state-card-icon">
              <UserRoundX size={25} strokeWidth={1.7} />
            </span>
            <h1>このユーザーは見つかりませんでした。</h1>
            <p>マシン一覧から別の作成者を選択してください。</p>
          </div>
        </section>
      )}
    </AppShell>
  )
}
