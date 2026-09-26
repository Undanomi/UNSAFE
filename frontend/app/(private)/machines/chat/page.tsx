import { ChatWorkspace } from "@/app/(private)/machines/chat/chat-workspace"
import { AppShell } from "@/components/app-shell"
import { NEW_CHAT_SESSION } from "@/stores/chat"

export default function NewMachineChatPage() {
  return (
    <AppShell artworkVariant="machines" layoutVariant="chat">
      <ChatWorkspace session={NEW_CHAT_SESSION} />
    </AppShell>
  )
}
