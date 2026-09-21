export function PageLoading() {
  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="surface-panel mono-label grid min-h-48 place-items-center rounded-2xl p-8 text-[var(--ink-soft)]"
      role="status"
    >
      読み込んでいます…
    </section>
  )
}
