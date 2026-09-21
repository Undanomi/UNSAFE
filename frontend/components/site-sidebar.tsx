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
import { ThemeToggle } from "@/components/theme-toggle"
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
  const isCreateActive = pathname.startsWith("/machines/chat")
  const isMachinesActive =
    pathname === "/machines" || (pathname.startsWith("/machines/") && !isCreateActive)

  function navItemClass(active: boolean) {
    return `relative flex items-center gap-2.5 rounded-lg border px-3 py-3 text-[0.86rem] font-bold transition-colors ${
      active
        ? "border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] before:absolute before:top-1/2 before:-left-[5px] before:size-2 before:-translate-y-1/2 before:bg-[var(--signal)]"
        : "border-transparent text-[var(--ink-soft)] hover:border-[var(--line)] hover:bg-[var(--surface)] hover:text-[var(--ink)]"
    }`
  }

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
    <aside className="fixed top-0 bottom-0 left-0 z-10 flex w-[234px] flex-col border-r border-[var(--line)] bg-[color-mix(in_srgb,var(--surface-muted)_92%,var(--surface))] px-4 py-5 text-[var(--ink)] max-lg:static max-lg:w-full max-lg:border-r-0 max-lg:border-b">
      <Link
        aria-label="マシン一覧へ"
        className="group mb-7 inline-flex items-start justify-between border-b border-[var(--line)] px-1 pt-1 pb-6"
        href="/machines"
      >
        <span>
          <span className="display-heading block text-[1.72rem] leading-none tracking-[-0.07em]">
            SLSG
          </span>
          <span className="mono-label mt-2 block text-[0.58rem] text-[var(--ink-soft)]">
            Security learning lab
          </span>
        </span>
        <span aria-hidden="true" className="mt-1 grid grid-cols-2 gap-[3px]">
          <span className="size-1.5 bg-[var(--signal)]" />
          <span className="size-1.5 bg-[var(--accent)]" />
          <span className="col-start-2 size-1.5 bg-[var(--signal)]" />
        </span>
      </Link>

      <nav aria-label="主要ナビゲーション" className="grid w-full gap-1.5">
        <Link className={navItemClass(isCreateActive)} href="/machines/chat">
          <CirclePlus aria-hidden="true" size={18} strokeWidth={2} />
          マシンを作る
        </Link>
        <Link className={navItemClass(isMachinesActive)} href="/machines">
          <LayoutList aria-hidden="true" size={18} strokeWidth={2} />
          マシン一覧
        </Link>
      </nav>

      <div className="mt-3 grid w-full gap-2.5 border-t border-[var(--line)] pt-3">
        <button
          aria-controls="sidebar-chat-list"
          aria-expanded={isChatListOpen}
          className="flex w-full items-center justify-between rounded-lg border border-transparent px-3 py-2.5 text-[0.8rem] font-bold text-[var(--ink-soft)] transition-colors hover:border-[var(--line)] hover:bg-[var(--surface)] hover:text-[var(--ink)]"
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
              <span className="px-[9px] py-2 text-[0.75rem] text-[var(--ink-faint)]">
                読み込み中…
              </span>
            ) : null}
            {!isLoadingChats && chatSessions.length === 0 ? (
              <span className="px-[9px] py-2 text-[0.75rem] text-[var(--ink-faint)]">
                保存済みのチャットはありません
              </span>
            ) : null}
            {chatSessions.map((session) => (
              <Link
                className="overflow-hidden rounded-md border-l-2 border-transparent px-[9px] py-2 text-[0.78rem] font-bold text-[var(--ink-soft)] text-ellipsis whitespace-nowrap hover:border-[var(--signal)] hover:bg-[var(--surface)] hover:text-[var(--ink)]"
                href={`/machines/chat/${session.id}`}
                key={session.id}
              >
                {session.name}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-[var(--line)] px-1 pt-4">
        <span className="mono-label text-[0.58rem] text-[var(--ink-faint)]">Interface</span>
        <ThemeToggle showLabel />
      </div>

      <div className="relative mt-3 flex w-full items-center gap-1 border-t border-[var(--line)] px-1 pt-4 pb-0.5">
        <Link
          aria-label="プロフィールを開く"
          className="inline-flex min-w-0 flex-1 items-center gap-[9px] text-[0.84rem] font-bold text-[var(--ink)]"
          href="/profile"
        >
          <span className="relative grid size-8 shrink-0 place-items-center overflow-hidden rounded-full border border-[var(--line-strong)] bg-[var(--inverse-surface)] text-sm text-[var(--inverse-ink)]">
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
          className="grid size-8 shrink-0 place-items-center rounded-lg border border-transparent text-[var(--ink-soft)] transition-colors hover:border-[var(--line)] hover:bg-[var(--surface)] hover:text-[var(--ink)]"
          onClick={() => setIsAccountMenuOpen((open) => !open)}
          type="button"
        >
          <Settings aria-hidden="true" size={17} strokeWidth={2} />
        </button>
        {isAccountMenuOpen ? (
          <div
            className="surface-panel absolute right-[5px] bottom-[calc(100%+8px)] left-[5px] rounded-xl p-1"
            id="sidebar-account-menu"
            role="menu"
          >
            <form action={logoutAction}>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-[0.82rem] font-bold text-[var(--ink)] transition-colors hover:bg-[var(--surface-muted)]"
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
