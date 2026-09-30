"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"
import { useEffect, useState } from "react"
import { DesignArtwork, MachineListHud } from "@/components/design-artwork"
import { SlsgBrand } from "@/components/slsg-brand"

export type LegalSection = {
  title: string
  body: ReactNode
}

function sectionTitle(title: string) {
  return title.replace(/^\d+\.\s*/, "")
}

function LegalSectionIndex({ index }: { index: number }) {
  return (
    <span aria-hidden="true" className="slsg-privacy-section-index">
      <svg fill="none" viewBox="0 0 92 100">
        <title>{`セクション${index}`}</title>
        <path className="slsg-privacy-section-index-halo" d="M46 2 85 25v50L46 98 7 75V25Z" />
        <path className="slsg-privacy-section-index-frame" d="M46 4 83 26v48L46 96 9 74V26Z" />
      </svg>
      <strong>{index}</strong>
    </span>
  )
}

export function LegalDocument({
  title,
  idPrefix,
  sections,
  tocLabels,
  lead,
}: {
  title: string
  idPrefix: string
  sections: LegalSection[]
  tocLabels: string[]
  lead: ReactNode
}) {
  const sectionId = (index: number) => `${idPrefix}-section-${index + 1}`
  const [activeSection, setActiveSection] = useState(1)

  useEffect(() => {
    const sectionId = (index: number) => `${idPrefix}-section-${index + 1}`
    const elements = sections
      .map((_, index) => document.getElementById(sectionId(index)))
      .filter((section): section is HTMLElement => section instanceof HTMLElement)
    let frameId: number | null = null

    const updateActiveSection = () => {
      frameId = null

      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
        setActiveSection(elements.length)
        return
      }

      const readingLine = Math.min(window.innerHeight * 0.28, 240)
      let nextActiveSection = 1

      for (const [index, section] of elements.entries()) {
        if (section.getBoundingClientRect().top > readingLine) break
        nextActiveSection = index + 1
      }

      setActiveSection((current) => (current === nextActiveSection ? current : nextActiveSection))
    }

    const scheduleActiveSectionUpdate = () => {
      if (frameId !== null) return
      frameId = window.requestAnimationFrame(updateActiveSection)
    }

    updateActiveSection()
    window.addEventListener("scroll", scheduleActiveSectionUpdate, { passive: true })
    window.addEventListener("resize", scheduleActiveSectionUpdate)

    return () => {
      window.removeEventListener("scroll", scheduleActiveSectionUpdate)
      window.removeEventListener("resize", scheduleActiveSectionUpdate)
      if (frameId !== null) window.cancelAnimationFrame(frameId)
    }
  }, [idPrefix, sections])

  return (
    <div className="slsg-shell slsg-shell-machines slsg-privacy-page">
      <aside className="slsg-sidebar slsg-privacy-sidebar">
        <SlsgBrand className="slsg-privacy-brand" href="/login" />
        <div className="slsg-privacy-sidebar-divider" />
        <p className="slsg-privacy-toc-heading">このページの内容</p>
        <nav aria-label={`${title}の目次`} className="slsg-privacy-toc">
          {tocLabels.map((label, index) => {
            const itemIndex = index + 1
            const isActive = activeSection === itemIndex
            return (
              <a
                aria-current={isActive ? "location" : undefined}
                className={isActive ? "is-active" : ""}
                href={`#${sectionId(index)}`}
                key={label}
                onClick={() => setActiveSection(itemIndex)}
              >
                <span>{String(itemIndex).padStart(2, "0")}</span>
                <strong>{label}</strong>
              </a>
            )
          })}
        </nav>
      </aside>

      <MachineListHud />
      <DesignArtwork variant="machines" />

      <main className="slsg-main slsg-privacy-main">
        <header className="slsg-privacy-header">
          <Link className="slsg-detail-back-link slsg-privacy-header-back" href="/login">
            <ArrowLeft aria-hidden="true" size={19} strokeWidth={1.8} />
            ログインへ戻る
          </Link>
          <h1 className="slsg-machine-page-title font-bold">{title}</h1>
          <p className="slsg-privacy-updated">最終更新日：2026年9月30日</p>
          <p className="slsg-machine-page-description slsg-muted slsg-privacy-lead">{lead}</p>
        </header>

        <article className="slsg-privacy-sections">
          {sections.map((section, index) => (
            <section
              className="slsg-privacy-section"
              data-section-index={index + 1}
              id={sectionId(index)}
              key={section.title}
            >
              <LegalSectionIndex index={index + 1} />
              <div className="slsg-privacy-section-content">
                <h2>{sectionTitle(section.title)}</h2>
                <div className="slsg-privacy-section-body">{section.body}</div>
              </div>
            </section>
          ))}
        </article>
      </main>
    </div>
  )
}
