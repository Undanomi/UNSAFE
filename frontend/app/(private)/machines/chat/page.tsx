import { ChatWorkspace } from "@/app/(private)/machines/chat/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { NEW_CHAT_SESSION } from "@/stores/chat"

export default function NewMachineChatPage() {
  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      <ChatWorkspace session={NEW_CHAT_SESSION} />
    </AppShell>
  )
}
