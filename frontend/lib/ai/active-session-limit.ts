import "server-only"

import type { AiActiveSessionLimitError } from "@/lib/ai/service"
import { listOwnedActiveChatLinksService } from "@/lib/chat/service"
import type { ActiveChatLink } from "@/stores/chat"

export type ActiveSessionLimitFailure = {
  success: false
  code: "active_session_limit"
  message: string
  activeChats: ActiveChatLink[]
}

export async function activeSessionLimitResult(
  ownerUserId: string,
  error: AiActiveSessionLimitError,
): Promise<ActiveSessionLimitFailure> {
  let activeChats: ActiveChatLink[] = []
  try {
    activeChats = await listOwnedActiveChatLinksService(ownerUserId, error.activeSessionIds)
  } catch (lookupError) {
    console.error("Failed to load active chat links.", lookupError)
  }
  return {
    success: false,
    code: "active_session_limit",
    message: `同時に作成できるマシンは${error.limit}つまでです。`,
    activeChats,
  }
}
