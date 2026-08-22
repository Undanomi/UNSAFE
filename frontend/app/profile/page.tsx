import { ProfileEditor } from "@/app/profile/_components/profile-editor"
import { AppShell } from "@/components/app-shell"

export default function ProfilePage() {
  return (
    <AppShell>
      <ProfileEditor showBackLink={false} />
    </AppShell>
  )
}
