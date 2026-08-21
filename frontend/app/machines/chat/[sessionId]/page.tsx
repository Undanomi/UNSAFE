import { ChatWorkspace, MissingChatSession } from "@/app/machines/chat/_components/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { chatSessions, newChatSession } from "@/stores/chat"

type ChatSessionPageProps = {
  params: Promise<{ sessionId: string }>
}

export default async function ChatSessionPage({ params }: ChatSessionPageProps) {
  const { sessionId } = await params
  const session =
    sessionId === newChatSession.id
      ? newChatSession
      : chatSessions.find((chatSession) => chatSession.id === sessionId)

  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      {session ? <ChatWorkspace key={session.id} session={session} /> : <MissingChatSession />}
    </AppShell>
  )
}
