import { ChatWorkspace } from "@/app/machines/chat/_components/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { newChatSession } from "@/stores/chat"

export default function NewMachineChatPage() {
  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      <ChatWorkspace session={newChatSession} />
    </AppShell>
  )
}
