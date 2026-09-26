"use client"

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { FlagCorrectArtwork } from "@/components/flag-correct-artwork"

export type FlagCorrectEffectProps = {
  open: boolean
  challengeName: string
  level?: number
  flagKind?: "user" | "system"
  points: number
  submittedFlag: string
  rank?: number
  totalPlayers?: number
  onClose: () => void
}

export function FlagCorrectEffect({
  open,
  challengeName,
  flagKind,
  onClose,
}: FlagCorrectEffectProps) {
  const [mounted, setMounted] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open || !mounted) return

    previousFocusRef.current = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    closeButtonRef.current?.focus({ preventScroll: true })

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== "Tab") return
      event.preventDefault()
      closeButtonRef.current?.focus()
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener("keydown", handleKeyDown)
      previousFocusRef.current?.focus({ preventScroll: true })
    }
  }, [mounted, open])

  if (!mounted || !open) return null

  const flagLabel =
    flagKind === "user" ? "ユーザーフラグ" : flagKind === "system" ? "システムフラグ" : "フラグ"
  const announcement = `正解です。${challengeName}の${flagLabel}を攻略しました。`

  return createPortal(
    <div
      aria-describedby="slsg-correct-summary"
      aria-labelledby="slsg-correct-title"
      aria-modal="true"
      className="slsg-correct-effect"
      onPointerDown={(event) => {
        if (event.currentTarget === event.target) onClose()
      }}
      ref={dialogRef}
      role="dialog"
      tabIndex={-1}
    >
      <FlagCorrectArtwork />
      <h2 className="sr-only" id="slsg-correct-title">
        FLAG CORRECT!
      </h2>
      <div className="slsg-correct-result-context" id="slsg-correct-summary">
        <p className="slsg-correct-machine-name">{challengeName}</p>
        <span aria-hidden="true" className="slsg-correct-result-divider" />
        <p className="slsg-correct-flag-kind">
          <span aria-hidden="true" className="slsg-correct-flag-indicator" />
          {flagLabel}
        </p>
      </div>
      <button
        aria-label="正解演出を閉じる"
        className="slsg-correct-close"
        onClick={onClose}
        ref={closeButtonRef}
        type="button"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20">
          <path d="m5 5 10 10M15 5 5 15" />
        </svg>
      </button>
      <p aria-live="assertive" className="sr-only" role="status">
        {announcement}
      </p>
    </div>,
    document.body,
  )
}
