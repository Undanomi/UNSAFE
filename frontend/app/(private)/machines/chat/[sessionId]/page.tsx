import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { ChatWorkspace, MissingChatSession } from "@/app/(private)/machines/chat/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants"
import { verifySessionCookieService } from "@/lib/auth/service"
import { getChatSessionPageService } from "@/lib/chat/service"

type ChatSessionPageProps = {
  params: Promise<{ sessionId: string }>
}

export default async function ChatSessionPage({ params }: ChatSessionPageProps) {
  const { sessionId } = await params
  const sessionCookie = (await cookies()).get(SESSION_COOKIE_NAME)?.value ?? ""
  const user = await verifySessionCookieService(sessionCookie)

  if (!user) redirect("/login")

  const session = await getChatSessionPageService(user.uid, sessionId)

  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      {session ? <ChatWorkspace key={session.id} session={session} /> : <MissingChatSession />}
    </AppShell>
  )
}
