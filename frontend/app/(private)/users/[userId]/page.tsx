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
