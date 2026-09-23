import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ProfileEditor } from "@/app/(private)/profile/profile-editor"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserProfileService } from "@/lib/users/service"

export default async function ProfilePage() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)

  if (!authenticatedUser) redirect("/login")

  const profile = await getUserProfileService(authenticatedUser.uid, authenticatedUser.uid)

  if (!profile) {
    throw new Error("Authenticated user profile was not found.")
  }

  return (
    <AppShell>
      <ProfileEditor profile={profile} showBackLink={false} />
    </AppShell>
  )
}
