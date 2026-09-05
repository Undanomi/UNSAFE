import { AppShell } from "@/components/app-shell"
import { PageLoading } from "@/components/page-loading"

export default function ChatSessionLoading() {
  return (
    <AppShell contentClassName="py-9 pb-14 max-lg:py-8">
      <PageLoading />
    </AppShell>
  )
}
