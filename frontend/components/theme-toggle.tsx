"use client"

import { Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"

type Theme = "light" | "dark"

type ThemeToggleProps = {
  className?: string
  showLabel?: boolean
}

const THEME_STORAGE_KEY = "slsg-theme"

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}

export function ThemeToggle({ className = "", showLabel = false }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme | null>(null)

  useEffect(() => {
    const rootTheme = document.documentElement.dataset.theme
    const currentTheme: Theme = rootTheme === "dark" ? "dark" : "light"
    setTheme(currentTheme)

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    const syncWithSystem = (event: MediaQueryListEvent) => {
      if (localStorage.getItem(THEME_STORAGE_KEY)) return
      const nextTheme = event.matches ? "dark" : "light"
      applyTheme(nextTheme)
      setTheme(nextTheme)
    }

    mediaQuery.addEventListener("change", syncWithSystem)
    return () => mediaQuery.removeEventListener("change", syncWithSystem)
  }, [])

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark"
    applyTheme(nextTheme)
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    setTheme(nextTheme)
  }

  const isDark = theme === "dark"

  return (
    <button
      aria-label={`${isDark ? "ライト" : "ダーク"}テーマに切り替える`}
      aria-pressed={isDark}
      className={`secondary-action inline-flex min-h-9 items-center justify-center gap-2 rounded-lg px-3 text-[0.78rem] font-bold ${className}`}
      onClick={toggleTheme}
      title={`${isDark ? "ライト" : "ダーク"}テーマに切り替える`}
      type="button"
    >
      {isDark ? (
        <Moon aria-hidden="true" className="text-[var(--signal)]" size={15} strokeWidth={2} />
      ) : (
        <Sun aria-hidden="true" className="text-[var(--accent)]" size={15} strokeWidth={2} />
      )}
      {showLabel ? <span>{isDark ? "Dark" : "Light"}</span> : null}
    </button>
  )
}
