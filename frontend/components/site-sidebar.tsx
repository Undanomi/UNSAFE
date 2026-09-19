"use client"

import {
  ChevronDown,
  ChevronUp,
  CirclePlus,
  LayoutList,
  LogOut,
  MessageSquare,
  Settings,
} from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { logoutAction } from "@/app/actions/auth"
import type { ChatSessionSummary } from "@/stores/chat"

type SiteSidebarProps = {
  user: {
    name: string
    avatarUrl: string
  }
}

export function SiteSidebar({ user }: SiteSidebarProps) {
  const [isChatListOpen, setIsChatListOpen] = useState(false)
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false)
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([])
  const [isLoadingChats, setIsLoadingChats] = useState(false)
  const pathname = usePathname()
  const userInitial = user.name.trim().charAt(0).toUpperCase() || "U"

  useEffect(() => {
    if (pathname) setIsChatListOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!isChatListOpen) return
    const abortController = new AbortController()

    async function loadChatSessions() {
      setIsLoadingChats(true)
      try {
        const response = await fetch("/api/chat/sessions", {
          cache: "no-store",
          signal: abortController.signal,
        })
        if (!response.ok) return
        const body = (await response.json()) as { sessions?: ChatSessionSummary[] }
        setChatSessions(body.sessions ?? [])
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          console.error("Failed to load chat sessions.", error)
        }
      } finally {
        if (!abortController.signal.aborted) setIsLoadingChats(false)
      }
    }

    void loadChatSessions()
    return () => abortController.abort()
  }, [isChatListOpen])

  return (
    <aside className="fixed top-0 bottom-0 left-0 z-10 flex w-[218px] flex-col border border-[#3d3d38] bg-[#20201e] px-[14px] py-5 text-[#f8f7f2] max-lg:static max-lg:w-full">
      <Link
        aria-label="マシン一覧へ"
        className="inline-flex items-center gap-2.5 px-[7px] pt-1 pb-[18px] text-[1.2rem] font-black tracking-[-0.06em] text-white"
        href="/machines"
      >
        <span className="grid size-[34px] place-items-center rounded-xl bg-white text-[1rem] tracking-normal text-[#20201e]">
          S
        </span>
        <span>SLSG</span>
      </Link>

      <nav aria-label="主要ナビゲーション" className="grid w-full gap-2">
        <Link
          className="flex items-center gap-2.5 rounded-[15px] border border-transparent p-3 text-[0.9rem] font-extrabold text-[#d1d0ca] transition-colors hover:border-[#55554e] hover:bg-[#2b2b28] hover:text-white"
          href="/machines/chat"
        >
          <CirclePlus aria-hidden="true" size={18} strokeWidth={2} />
          マシンを作る
        </Link>
        <Link
          className="flex items-center gap-2.5 rounded-[15px] border border-transparent p-3 text-[0.9rem] font-extrabold text-[#d1d0ca] transition-colors hover:border-[#55554e] hover:bg-[#2b2b28] hover:text-white"
          href="/machines"
        >
          <LayoutList aria-hidden="true" size={18} strokeWidth={2} />
          マシン一覧
        </Link>
      </nav>

      <div className="mt-2.5 grid w-full gap-2.5">
        <button
          aria-controls="sidebar-chat-list"
          aria-expanded={isChatListOpen}
          className="flex w-full items-center justify-between rounded-[13px] border border-transparent px-[11px] py-2.5 text-[0.82rem] font-extrabold text-[#d1d0ca] transition-colors hover:border-[#55554e] hover:bg-[#2b2b28] hover:text-white"
          onClick={() => setIsChatListOpen((open) => !open)}
          type="button"
        >
          <span className="flex items-center gap-2.5">
            <MessageSquare aria-hidden="true" size={18} strokeWidth={2} />
            チャット一覧
          </span>
          {isChatListOpen ? (
            <ChevronUp aria-hidden="true" size={17} strokeWidth={2} />
          ) : (
            <ChevronDown aria-hidden="true" size={17} strokeWidth={2} />
          )}
        </button>
        {isChatListOpen ? (
          <nav
            aria-label="作成チャット一覧"
            className="grid max-h-[156px] gap-[5px] overflow-y-auto pr-0.5"
            id="sidebar-chat-list"
          >
            {isLoadingChats ? (
              <span className="px-[9px] py-2 text-[0.75rem] text-[#aaa9a3]">読み込み中…</span>
            ) : null}
            {!isLoadingChats && chatSessions.length === 0 ? (
              <span className="px-[9px] py-2 text-[0.75rem] text-[#aaa9a3]">
                保存済みのチャットはありません
              </span>
            ) : null}
            {chatSessions.map((session) => (
              <Link
                className="overflow-hidden rounded-[10px] px-[9px] py-2 text-[0.78rem] font-bold text-[#c5c4bd] text-ellipsis whitespace-nowrap hover:bg-[#3a3934] hover:text-white"
                href={`/machines/chat/${session.id}`}
                key={session.id}
              >
                {session.name}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>

      <div className="relative mt-auto flex w-full items-center gap-1 border-t border-[#44443f] px-[5px] pt-3 pb-0.5">
        <Link
          aria-label="プロフィールを開く"
          className="inline-flex min-w-0 flex-1 items-center gap-[9px] text-[0.86rem] font-extrabold text-[#f8f7f2]"
          href="/profile"
        >
          <span className="relative grid size-8 shrink-0 place-items-center overflow-hidden rounded-full border border-[#50504b] bg-[#20201e] text-sm text-white">
            {user.avatarUrl ? (
              <Image
                alt={`${user.name}のプロフィール画像`}
                fill
                className="size-full object-cover"
                loading="eager"
                referrerPolicy="no-referrer"
                sizes="32px"
                src={user.avatarUrl}
                unoptimized
              />
            ) : (
              userInitial
            )}
          </span>
          <span className="truncate">{user.name}</span>
        </Link>
        <button
          aria-controls="sidebar-account-menu"
          aria-expanded={isAccountMenuOpen}
          aria-label="アカウント設定を開く"
          className="grid size-8 shrink-0 place-items-center rounded-lg border border-transparent text-[#c5c4bd] transition-colors hover:border-[#55554e] hover:bg-[#2b2b28] hover:text-white"
          onClick={() => setIsAccountMenuOpen((open) => !open)}
          type="button"
        >
          <Settings aria-hidden="true" size={17} strokeWidth={2} />
        </button>
        {isAccountMenuOpen ? (
          <div
            className="absolute right-[5px] bottom-[calc(100%+8px)] left-[5px] rounded-xl border border-[#55554e] bg-[#292926] p-1 shadow-lg"
            id="sidebar-account-menu"
            role="menu"
          >
            <form action={logoutAction}>
              <button
                className="flex w-full items-center gap-2 rounded-[9px] px-3 py-2.5 text-[0.82rem] font-extrabold text-[#f4f3ee] transition-colors hover:bg-[#3a3934]"
                role="menuitem"
                type="submit"
              >
                <LogOut aria-hidden="true" size={16} strokeWidth={2} />
                ログアウト
              </button>
            </form>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
