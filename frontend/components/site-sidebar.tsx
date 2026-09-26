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
import { SlsgBrand } from "@/components/slsg-brand"
import type { ChatSessionSummary } from "@/stores/chat"

type SiteSidebarProps = {
  user: {
    id: string
    name: string
    avatarUrl: string
  }
}

export function SiteSidebar({ user }: SiteSidebarProps) {
  const pathname = usePathname()
  const [isChatListOpen, setIsChatListOpen] = useState(false)
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false)
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([])
  const [isLoadingChats, setIsLoadingChats] = useState(false)
  const userInitial = user.name.trim().charAt(0).toUpperCase() || "U"
  const isCreateActive = pathname === "/machines/chat"
  const isMachineListActive =
    pathname === "/machines" ||
    (!pathname.startsWith("/machines/chat") && /^\/machines\/[^/]+$/.test(pathname))

  useEffect(() => {
    if (!user.id) return
    try {
      setIsChatListOpen(localStorage.getItem(`slsg:chat-list-open:${user.id}`) === "true")
    } catch {
      setIsChatListOpen(false)
    }
  }, [user.id])

  function toggleChatList() {
    const nextIsOpen = !isChatListOpen
    setIsChatListOpen(nextIsOpen)
    if (!user.id) return
    try {
      localStorage.setItem(`slsg:chat-list-open:${user.id}`, String(nextIsOpen))
    } catch {
      // Keep the current page interactive when browser storage is unavailable.
    }
  }

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
    <aside className="slsg-sidebar slsg-app-sidebar fixed inset-y-0 left-0 z-20 flex flex-col text-[#eef5ff] max-lg:static">
      <SlsgBrand className="mx-6 mt-6 mb-9 shrink-0" />

      <nav
        aria-label="主要ナビゲーション"
        className="slsg-sidebar-primary-nav grid w-full shrink-0 gap-1"
      >
        <Link
          aria-current={isCreateActive ? "page" : undefined}
          className={`slsg-sidebar-link ${isCreateActive ? "is-active" : ""}`}
          href="/machines/chat"
        >
          <CirclePlus aria-hidden="true" size={18} strokeWidth={2} />
          マシン作成
        </Link>
        <Link
          aria-current={isMachineListActive ? "page" : undefined}
          className={`slsg-sidebar-link ${isMachineListActive ? "is-active" : ""}`}
          href="/machines"
        >
          <LayoutList aria-hidden="true" size={18} strokeWidth={2} />
          マシン一覧
        </Link>
      </nav>

      <div className="slsg-sidebar-chat-section mt-1 w-full gap-1">
        <button
          aria-controls="sidebar-chat-list"
          aria-expanded={isChatListOpen}
          className="slsg-sidebar-link w-full shrink-0 justify-between"
          onClick={toggleChatList}
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
            className="slsg-sidebar-chat-list mx-7 grid gap-1 overflow-y-auto border-l border-[#253654] py-1 pl-4"
            id="sidebar-chat-list"
          >
            {isLoadingChats ? (
              <span className="px-[9px] py-2 text-[0.75rem] text-[#8292aa]">読み込み中…</span>
            ) : null}
            {!isLoadingChats && chatSessions.length === 0 ? (
              <span className="px-[9px] py-2 text-[0.75rem] text-[#8292aa]">
                保存済みのチャットはありません
              </span>
            ) : null}
            {chatSessions.map((session) => {
              const href = `/machines/chat/${session.id}`
              const isActive = pathname === href

              return (
                <Link
                  aria-current={isActive ? "page" : undefined}
                  className={`slsg-chat-session-link ${isActive ? "is-active" : ""}`}
                  href={href}
                  key={session.id}
                >
                  {session.name}
                </Link>
              )
            })}
          </nav>
        ) : null}
      </div>

      <div className="slsg-sidebar-account relative mt-auto flex w-full shrink-0 items-center gap-1 border-t border-[#20304d] px-6 py-5">
        <Link
          aria-label="プロフィールを開く"
          className="inline-flex min-w-0 flex-1 items-center gap-3 text-sm font-bold text-[#eef5ff]"
          href="/profile"
        >
          <span className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full border border-[#50617e] bg-[#273651] text-sm text-white">
            {user.avatarUrl ? (
              <Image
                alt={`${user.name}のプロフィール画像`}
                fill
                className="size-full object-cover"
                loading="eager"
                referrerPolicy="no-referrer"
                sizes="40px"
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
          className="grid size-9 shrink-0 place-items-center rounded-lg border border-transparent text-[#9cabc1] transition-colors hover:border-[#3c5273] hover:bg-[#14233d] hover:text-white"
          onClick={() => setIsAccountMenuOpen((open) => !open)}
          type="button"
        >
          <Settings aria-hidden="true" size={17} strokeWidth={2} />
        </button>
        {isAccountMenuOpen ? (
          <div
            className="absolute right-5 bottom-[calc(100%+8px)] left-5 rounded-xl border border-[#40577a] bg-[#111d33] p-1 shadow-2xl shadow-black/40"
            id="sidebar-account-menu"
            role="menu"
          >
            <form action={logoutAction}>
              <button
                className="flex w-full items-center gap-2 rounded-[9px] px-3 py-2.5 text-sm font-bold text-[#eef5ff] transition-colors hover:bg-[#1b2c49]"
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
