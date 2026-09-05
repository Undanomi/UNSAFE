import { ChatWorkspace, MissingChatSession } from "@/app/(private)/machines/chat/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { CHAT_SESSIONS, NEW_CHAT_SESSION } from "@/stores/chat"

type ChatSessionPageProps = {
  params: Promise<{ sessionId: string }>
}

export default async function ChatSessionPage({ params }: ChatSessionPageProps) {
  const { sessionId } = await params
  const session =
    sessionId === NEW_CHAT_SESSION.id
      ? NEW_CHAT_SESSION
      : CHAT_SESSIONS.find((chatSession) => chatSession.id === sessionId)

  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      {session ? <ChatWorkspace key={session.id} session={session} /> : <MissingChatSession />}
    </AppShell>
  )
}
