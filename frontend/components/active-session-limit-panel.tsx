import { AlertCircle } from "lucide-react"
import Link from "next/link"
import type { ActiveChatLink } from "@/stores/chat"

export type ActiveLimitNotice = { message: string; activeChats: ActiveChatLink[] }

export function ActiveSessionLimitPanel({ notice }: { notice: ActiveLimitNotice }) {
  return (
    <div className="slsg-active-session-limit" role="alert">
      <p className="flex items-center gap-2 font-bold">
        <AlertCircle aria-hidden="true" size={18} />
        {notice.message}
      </p>
      {notice.activeChats.length > 0 ? (
        <div className="slsg-active-session-limit-links">
          <p>現在作成中のチャット</p>
          <ul>
            {notice.activeChats.map((chat) => (
              <li key={chat.id}>
                <Link href={`/machines/chat/${encodeURIComponent(chat.id)}`}>{chat.name}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
