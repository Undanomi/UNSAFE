import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ProfileSetupForm } from "@/app/(private)/profile/setup/profile-setup-form"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getOrCreateUserDocumentService } from "@/lib/users/service"

export default async function ProfileSetupPage() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)

  if (!authenticatedUser) redirect("/login")

  const userDocument = await getOrCreateUserDocumentService(authenticatedUser)
  if (userDocument.profile_completed === true) redirect("/machines")

  return (
    <ProfileSetupForm
      initialIconUrl={userDocument.icon_url || authenticatedUser.picture || ""}
      initialName={userDocument.name || authenticatedUser.name}
    />
  )
}
