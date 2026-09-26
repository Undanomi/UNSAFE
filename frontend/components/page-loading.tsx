import { LoaderCircle } from "lucide-react"

export function PageLoading() {
  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="slsg-panel slsg-state-card is-loading"
      role="status"
    >
      <div className="slsg-state-card-content">
        <span aria-hidden="true" className="slsg-state-card-icon">
          <LoaderCircle className="animate-spin" size={27} strokeWidth={1.7} />
        </span>
        <p className="slsg-state-card-title">読み込んでいます…</p>
        <span aria-hidden="true" className="slsg-state-loading-track">
          <i />
        </span>
      </div>
    </section>
  )
}
