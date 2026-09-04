import { ProfileEditor } from "@/app/(private)/profile/profile-editor"
import { AppShell } from "@/components/app-shell"

export default function ProfilePage() {
  return (
    <AppShell>
      <ProfileEditor showBackLink={false} />
    </AppShell>
  )
}
