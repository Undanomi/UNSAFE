import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ProfileSetupForm } from "@/app/(private)/profile/setup/profile-setup-form"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserDocumentService } from "@/lib/users/service"

export default async function ProfileSetupPage() {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)

  if (!authenticatedUser) redirect("/login")

  const userDocument = await getUserDocumentService(authenticatedUser.uid)
  if (!userDocument) throw new Error("Authenticated user document was not found.")
  if (userDocument.profile_completed === true) redirect("/machines")

  return (
    <ProfileSetupForm
      initialIconUrl={userDocument.icon_url || authenticatedUser.picture || ""}
      initialName={userDocument.name || authenticatedUser.name}
    />
  )
}
