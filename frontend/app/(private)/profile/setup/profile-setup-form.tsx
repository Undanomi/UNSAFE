"use client"

import { ArrowRight } from "lucide-react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { type FormEvent, useState } from "react"
import { logoutAction } from "@/app/actions/auth"
import { completeProfileAction } from "@/app/actions/profile"
import { DesignArtwork } from "@/components/design-artwork"
import { UnsafeBrandSymbol } from "@/components/slsg-brand"

type ProfileSetupFormProps = {
  initialName: string
  initialIconUrl: string
}

function SetupBrand() {
  return (
    <div className="slsg-profile-setup-brand">
      <span aria-hidden="true">
        <UnsafeBrandSymbol />
      </span>
      <strong>UNSAFE</strong>
    </div>
  )
}

type AvatarPreviewProps = {
  iconMode: "google" | "initial"
  initial: string
  initialIconUrl: string
  name: string
}

function AvatarPreview({ iconMode, initial, initialIconUrl, name }: AvatarPreviewProps) {
  return (
    <div aria-label="アイコンのプレビュー" className="slsg-setup-avatar" role="img">
      <svg aria-hidden="true" viewBox="0 0 286 286">
        <defs>
          <linearGradient id="setup-avatar-fill" x1="0" x2="1" y1="0" y2="1">
            <stop stopColor="#4f8af0" />
            <stop offset="1" stopColor="#3e70dc" />
          </linearGradient>
          <linearGradient id="setup-avatar-line" x1="0" x2="1" y1="0" y2="1">
            <stop stopColor="#55e4ee" />
            <stop offset="0.56" stopColor="#5795ef" />
            <stop offset="1" stopColor="#55e4ee" />
          </linearGradient>
          <filter id="setup-avatar-glow" height="180%" width="180%" x="-40%" y="-40%">
            <feGaussianBlur result="blur" stdDeviation="6" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id="setup-avatar-content-clip" clipPathUnits="objectBoundingBox">
            <path d="M.526.015.907.235Q.933.25.933.28V.72Q.933.75.907.765L.526.985Q.5 1 .474.985L.093.765Q.067.75.067.72V.28Q.067.25.093.235L.474.015Q.5 0 .526.015Z" />
          </clipPath>
        </defs>
        <path
          d="M150.02 12.05 252.9 71.45Q259.91 75.5 259.91 83.6v118.8q0 8.1-7.01 12.15l-102.88 59.4Q143 278 135.98 273.95L33.1 214.55q-7.01-4.05-7.01-12.15V83.6q0-8.1 7.01-12.15l102.88-59.4Q143 8 150.02 12.05Z"
          fill="none"
          filter="url(#setup-avatar-glow)"
          stroke="url(#setup-avatar-line)"
          strokeLinejoin="round"
          strokeWidth="6"
        />
        <path
          d="M149.5 21.75 244.76 76.75Q251.25 80.5 251.25 88v110q0 7.5-6.49 11.25l-95.26 55Q143 268 136.5 264.25l-95.26-55q-6.49-3.75-6.49-11.25V88q0-7.5 6.49-11.25l95.26-55Q143 18 149.5 21.75Z"
          fill="url(#setup-avatar-fill)"
        />
      </svg>
      <span className="slsg-setup-avatar-content">
        {iconMode === "google" && initialIconUrl ? (
          <Image
            alt={`${name || "ユーザー"}のGoogleプロフィール画像`}
            fill
            className="object-cover"
            sizes="240px"
            src={initialIconUrl}
            unoptimized
          />
        ) : (
          initial
        )}
      </span>
    </div>
  )
}

export function ProfileSetupForm({ initialName, initialIconUrl }: ProfileSetupFormProps) {
  const router = useRouter()
  const [name, setName] = useState(initialName)
  const [iconMode, setIconMode] = useState<"google" | "initial">(
    initialIconUrl ? "google" : "initial",
  )
  const [error, setError] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  const initial = name.trim().charAt(0).toUpperCase() || "U"

  async function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSaving) return

    setError("")
    setIsSaving(true)

    try {
      const formData = new FormData()
      formData.set("name", name)
      formData.set("icon_mode", iconMode)

      const result = await completeProfileAction(formData)
      if (!result.success) {
        setError(result.message)
        return
      }

      router.replace("/machines")
      router.refresh()
    } catch {
      setError("プロフィールを登録できませんでした。もう一度お試しください。")
    } finally {
      setIsSaving(false)
    }
  }

  function switchGoogleAccount() {
    void logoutAction()
  }

  return (
    <main className="slsg-profile-setup-page">
      <DesignArtwork variant="machines" />
      <SetupBrand />

      <section className="slsg-profile-setup-intro">
        <p className="slsg-profile-setup-kicker">Account Setup</p>
        <span aria-hidden="true" className="slsg-profile-setup-rule" />
        <h1>
          あなたらしい
          <br />
          プロフィールを
          <br />
          作りましょう。
        </h1>
        <p className="slsg-profile-setup-description">
          名前とアイコンの表示方法は、
          <br />
          あとから変更できます。
        </p>
        <button className="slsg-profile-setup-switch" onClick={switchGoogleAccount} type="button">
          別のGoogleアカウントでログイン
          <ArrowRight aria-hidden="true" size={21} strokeWidth={1.7} />
        </button>
      </section>

      <section aria-labelledby="profile-setup-heading" className="slsg-profile-setup-card">
        <i aria-hidden="true" className="slsg-setup-corner slsg-setup-corner-tl" />
        <i aria-hidden="true" className="slsg-setup-corner slsg-setup-corner-tr" />
        <i aria-hidden="true" className="slsg-setup-corner slsg-setup-corner-bl" />
        <i aria-hidden="true" className="slsg-setup-corner slsg-setup-corner-br" />
        <i aria-hidden="true" className="slsg-setup-side-glow slsg-setup-side-glow-left" />
        <i aria-hidden="true" className="slsg-setup-side-glow slsg-setup-side-glow-right" />

        <header className="slsg-profile-setup-card-header">
          <h2 id="profile-setup-heading">プロフィール登録</h2>
          <p>他のユーザーに表示される名前を設定します。</p>
        </header>

        <form className="slsg-profile-setup-form" onSubmit={submitProfile}>
          <div className="slsg-profile-setup-options">
            <section className="slsg-profile-setup-preview">
              <h3>アイコンのプレビュー</h3>
              <AvatarPreview
                iconMode={iconMode}
                initial={initial}
                initialIconUrl={initialIconUrl}
                name={name}
              />
            </section>

            <fieldset className="slsg-profile-setup-modes">
              <legend>アイコンの表示方法</legend>
              <label className={iconMode === "google" ? "is-selected" : ""}>
                <input
                  checked={iconMode === "google"}
                  disabled={!initialIconUrl}
                  name="icon-mode"
                  onChange={() => setIconMode("google")}
                  type="radio"
                />
                <span aria-hidden="true" className="slsg-setup-radio" />
                <span className="slsg-setup-mode-copy">
                  <strong>Googleアイコン</strong>
                  <small>Googleアカウントのプロフィール画像を使用します。</small>
                </span>
              </label>
              <label className={iconMode === "initial" ? "is-selected" : ""}>
                <input
                  checked={iconMode === "initial"}
                  name="icon-mode"
                  onChange={() => setIconMode("initial")}
                  type="radio"
                />
                <span aria-hidden="true" className="slsg-setup-radio" />
                <span className="slsg-setup-mode-copy">
                  <strong>イニシャル</strong>
                  <small>名前のイニシャルを表示します。</small>
                </span>
              </label>
            </fieldset>
          </div>

          <div className="slsg-profile-setup-controls">
            <label className="slsg-profile-setup-name">
              <span>ユーザー名</span>
              <span className="slsg-profile-setup-input-wrap">
                <input
                  aria-describedby={error ? "profile-setup-error" : undefined}
                  aria-invalid={error ? true : undefined}
                  autoComplete="nickname"
                  maxLength={30}
                  onChange={(event) => setName(event.target.value)}
                  required
                  value={name}
                />
                <small>{name.length} / 30</small>
              </span>
            </label>

            {error ? (
              <p className="slsg-profile-setup-error" id="profile-setup-error" role="alert">
                {error}
              </p>
            ) : null}

            <button className="slsg-profile-setup-submit" disabled={isSaving} type="submit">
              <span>{isSaving ? "登録しています…" : "このプロフィールではじめる"}</span>
              {!isSaving ? <ArrowRight aria-hidden="true" size={22} strokeWidth={1.8} /> : null}
            </button>
          </div>
        </form>
      </section>
    </main>
  )
}
