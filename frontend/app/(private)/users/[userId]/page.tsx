import { ProfileEditor } from "@/app/(private)/profile/profile-editor"
import { AppShell } from "@/components/app-shell"
import { USER_PROFILES } from "@/stores/profile"

type UserPageProps = {
  params: Promise<{ userId: string }>
}

export default async function UserPage({ params }: UserPageProps) {
  const { userId } = await params
  const profile = USER_PROFILES[userId]

  return (
    <AppShell>
      {profile ? (
        <ProfileEditor canEdit={false} key={profile.id} profile={profile} />
      ) : (
        <section className="surface-panel signal-corner grid gap-3 rounded-2xl p-8">
          <p className="mono-label text-[var(--signal)]">Lookup failed / 404</p>
          <h1 className="display-heading text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05]">
            このユーザーは見つかりませんでした。
          </h1>
          <p className="leading-[1.65] text-[var(--ink-soft)]">
            マシン一覧から別の作成者を選択してください。
          </p>
        </section>
      )}
    </AppShell>
  )
}
