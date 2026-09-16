import { cookies } from "next/headers"
import type { ReactNode } from "react"
import { SiteSidebar } from "@/components/site-sidebar"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserDocumentService } from "@/lib/users/service"

type AppShellProps = {
  children: ReactNode
  contentClassName?: string
}

export async function AppShell({ children, contentClassName = "" }: AppShellProps) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)
  const userDocument = authenticatedUser
    ? await getUserDocumentService(authenticatedUser.uid)
    : null
  const sidebarUser = {
    name: userDocument?.name || authenticatedUser?.name || "ユーザー",
    avatarUrl: userDocument ? userDocument.icon_url : authenticatedUser?.picture || "",
  }

  return (
    <div className="min-h-screen bg-white">
      <SiteSidebar user={sidebarUser} />
      <main
        className={`mx-auto w-[min(1180px,calc(100%-368px))] py-12 pb-[72px] lg:mr-12 max-lg:w-full max-lg:px-6 max-lg:py-8 max-sm:px-4 ${contentClassName}`}
      >
        {children}
      </main>
    </div>
  )
}
