import { cookies } from "next/headers"
import type { ReactNode } from "react"
import {
  CircuitFrame,
  DesignArtwork,
  HudCornerDecoration,
  MachineListHud,
} from "@/components/design-artwork"
import { SiteSidebar } from "@/components/site-sidebar"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getUserDocumentService } from "@/lib/users/service"

type AppShellProps = {
  children: ReactNode
  contentClassName?: string
  artworkVariant?: "infrastructure" | "machines"
  layoutVariant?: "chat" | "default" | "machine-detail" | "profile"
}

export async function AppShell({
  children,
  contentClassName = "",
  artworkVariant = "infrastructure",
  layoutVariant = "default",
}: AppShellProps) {
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const authenticatedUser = await verifySessionCookieService(sessionCookie)
  const userDocument = authenticatedUser
    ? await getUserDocumentService(authenticatedUser.uid)
    : null
  const sidebarUser = {
    id: authenticatedUser?.uid ?? "",
    name: userDocument?.name || authenticatedUser?.name || "ユーザー",
    avatarUrl: userDocument ? userDocument.icon_url : authenticatedUser?.picture || "",
  }

  return (
    <div
      className={`slsg-shell slsg-app-shell ${layoutVariant === "chat" ? "slsg-chat-shell" : "min-h-screen"} ${artworkVariant === "machines" ? "slsg-shell-machines" : ""} ${layoutVariant === "machine-detail" ? "slsg-machine-detail-shell" : ""} ${layoutVariant === "profile" ? "slsg-profile-shell" : ""}`}
    >
      <SiteSidebar user={sidebarUser} />
      {artworkVariant === "machines" ? (
        <>
          <MachineListHud />
          <HudCornerDecoration />
        </>
      ) : (
        <CircuitFrame />
      )}
      <DesignArtwork variant={artworkVariant} />
      <main
        className={`slsg-main slsg-app-main relative z-[1] ${layoutVariant === "chat" ? "" : "min-h-screen"} px-[clamp(26px,3vw,54px)] py-9 pb-16 max-lg:px-6 max-lg:py-8 max-sm:px-4 ${contentClassName}`}
      >
        {children}
      </main>
    </div>
  )
}
