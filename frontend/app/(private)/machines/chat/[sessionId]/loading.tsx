import { AppShell } from "@/components/app-shell"
import { ChatLoadingSkeleton } from "@/components/chat-loading-skeleton"

export default function ChatSessionLoading() {
  return (
    <AppShell artworkVariant="machines" layoutVariant="chat">
      <ChatLoadingSkeleton />
    </AppShell>
  )
}
