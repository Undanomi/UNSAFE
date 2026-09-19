import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ProfileEditor } from "@/app/(private)/profile/profile-editor"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserDocumentService } from "@/lib/users/service"

export default async function ProfilePage() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)

  if (!authenticatedUser) redirect("/login")

  const user = await getUserDocumentService(authenticatedUser.uid)

  if (!user) {
    throw new Error("Authenticated user document was not found.")
  }

  const profile = {
    id: user.id,
    name: user.name,
    initial: user.name.trim().charAt(0).toUpperCase() || "U",
    bio: user.bio,
    avatarUrl: user.icon_url,
    createdMachines: [],
    solvedMachines: [],
  }

  return (
    <AppShell>
      <ProfileEditor profile={profile} showBackLink={false} />
    </AppShell>
  )
}
