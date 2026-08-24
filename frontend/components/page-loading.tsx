export function PageLoading() {
  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="grid min-h-48 place-items-center rounded-3xl border border-[#e5e5e2] bg-white p-8 text-[#61605b] shadow-sm"
      role="status"
    >
      読み込んでいます…
    </section>
  )
}
