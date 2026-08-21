import type { ReactNode } from "react"
import { SiteSidebar } from "@/components/site-sidebar"

type AppShellProps = {
  children: ReactNode
  contentClassName?: string
}

export function AppShell({ children, contentClassName = "" }: AppShellProps) {
  return (
    <div className="min-h-screen bg-white">
      <SiteSidebar />
      <main
        className={`mx-auto w-[min(1180px,calc(100%-368px))] py-12 pb-[72px] lg:mr-12 max-lg:w-full max-lg:px-6 max-lg:py-8 max-sm:px-4 ${contentClassName}`}
      >
        {children}
      </main>
    </div>
  )
}
