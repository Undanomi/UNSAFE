"use client"

import {
  type Auth,
  GoogleAuthProvider,
  inMemoryPersistence,
  setPersistence,
  signInWithPopup,
  signOut,
} from "firebase/auth"
import { Box, List, Terminal } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { FcGoogle } from "react-icons/fc"
import { createSessionAction } from "@/app/actions/auth"
import { DesignArtwork } from "@/components/design-artwork"
import { SlsgBrand } from "@/components/slsg-brand"
import { getFirebaseAuth } from "@/lib/firebase/client"
import { LOGIN_COPY } from "@/stores/login"

export function LoginForm() {
  const router = useRouter()
  const [error, setError] = useState("")
  const [isGoogleSigningIn, setIsGoogleSigningIn] = useState(false)

  async function handleGoogleSignIn() {
    setError("")
    setIsGoogleSigningIn(true)
    let auth: Auth | undefined

    try {
      auth = getFirebaseAuth()
      await setPersistence(auth, inMemoryPersistence)
      const credential = await signInWithPopup(auth, new GoogleAuthProvider())
      const result = await createSessionAction(await credential.user.getIdToken())

      if (!result.success) {
        setError(result.message)
        return
      }

      router.replace(result.redirectTo)
      router.refresh()
    } catch {
      setError("Google ログインに失敗しました。もう一度お試しください。")
    } finally {
      if (auth?.currentUser) {
        await signOut(auth).catch(() => undefined)
      }
      setIsGoogleSigningIn(false)
    }
  }

  return (
    <main className="slsg-login-page">
      <header className="slsg-login-header">
        <SlsgBrand href="/login" variant="orbit" />
      </header>

      <div className="slsg-login-layout">
        <section className="slsg-login-hero">
          <p className="slsg-login-kicker">SECURITY LEARNING</p>
          <h1 className="slsg-login-title">{LOGIN_COPY.title}</h1>
          <p className="slsg-login-description">{LOGIN_COPY.description}</p>

          <div className="slsg-login-flow">
            {["first", "second"].map((position) => (
              <svg
                aria-hidden="true"
                className={`slsg-login-flow-connector is-${position}`}
                key={position}
                preserveAspectRatio="none"
                viewBox="0 0 100 14"
              >
                <path
                  className="slsg-login-flow-connector-glow"
                  d="M0 0H35.5L41.5 14H58.5L64.5 0H100"
                  vectorEffect="non-scaling-stroke"
                />
                <path d="M0 0H35.5L41.5 14H58.5L64.5 0H100" vectorEffect="non-scaling-stroke" />
              </svg>
            ))}
            {[
              { id: "theme", icon: List, label: "テーマ", text: "学びたい内容を選ぶ" },
              { id: "machine", icon: Box, label: "マシン", text: "最適な環境を作成" },
              { id: "learning", icon: Terminal, label: "学習", text: "実際に手を動かして理解" },
            ].map(({ id, icon: Icon, label, text }) => (
              <div className="slsg-login-flow-item" key={label}>
                <span className="slsg-login-flow-icon">
                  <svg aria-hidden="true" className="slsg-login-flow-hex" viewBox="0 0 90 90">
                    <title>{`${label}のアイコン枠`}</title>
                    <defs>
                      <linearGradient
                        id={`slsg-login-flow-${id}-border`}
                        gradientUnits="userSpaceOnUse"
                        x1="0"
                        x2="90"
                        y1="0"
                        y2="90"
                      >
                        <stop offset="0" stopColor="#c5f8ff" />
                        <stop offset="0.3" stopColor="#78bfd5" />
                        <stop offset="0.66" stopColor="#5698ff" />
                        <stop offset="1" stopColor="#304e8e" stopOpacity="0.52" />
                      </linearGradient>
                      <linearGradient
                        id={`slsg-login-flow-${id}-glow-upper`}
                        gradientUnits="userSpaceOnUse"
                        x1="45"
                        x2="7"
                        y1="2"
                        y2="37"
                      >
                        <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                        <stop offset="0.34" stopColor="#78bfd5" stopOpacity="0.42" />
                        <stop offset="0.68" stopColor="#c5f8ff" />
                        <stop offset="0.84" stopColor="#78bfd5" stopOpacity="0.34" />
                        <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
                      </linearGradient>
                      <linearGradient
                        id={`slsg-login-flow-${id}-glow-lower`}
                        gradientUnits="userSpaceOnUse"
                        x1="83"
                        x2="49"
                        y1="53"
                        y2="87"
                      >
                        <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                        <stop offset="0.16" stopColor="#78bfd5" stopOpacity="0.38" />
                        <stop offset="0.32" stopColor="#c5f8ff" />
                        <stop offset="0.62" stopColor="#78bfd5" stopOpacity="0.38" />
                        <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <path
                      className="slsg-login-flow-hex-outer"
                      d="M45 2q2 0 4 1l31 18q3 2 3 6v36q0 4-3 6L49 87q-4 2-8 0L10 69q-3-2-3-6V27q0-4 3-6L41 3q2-1 4-1Z"
                      stroke={`url(#slsg-login-flow-${id}-border)`}
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      className="slsg-login-flow-hex-inner"
                      d="M45 9q2 0 4 1l25 15q3 2 3 5v30q0 3-3 5L49 80q-4 2-8 0L16 65q-3-2-3-5V30q0-3 3-5l25-15q2-1 4-1Z"
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      className="slsg-login-flow-hex-glow"
                      d="M45 2 10 21q-3 2-3 6v10"
                      stroke={`url(#slsg-login-flow-${id}-glow-upper)`}
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      className="slsg-login-flow-hex-glow"
                      d="M83 53v10q0 4-3 6L49 87"
                      stroke={`url(#slsg-login-flow-${id}-glow-lower)`}
                      vectorEffect="non-scaling-stroke"
                    />
                  </svg>
                  <span className="slsg-login-flow-glyph">
                    <Icon aria-hidden="true" size={27} strokeWidth={1.55} />
                  </span>
                </span>
                <strong>{label}</strong>
                <span>{text}</span>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="login-heading" className="slsg-login-card-wrap">
          <div className="slsg-login-card">
            <DesignArtwork className="slsg-login-security-art" variant="security" />
            <h2 className="slsg-login-card-title" id="login-heading">
              {LOGIN_COPY.auth.title}
            </h2>
            <p className="slsg-login-card-description">{LOGIN_COPY.auth.description}</p>
            {error ? (
              <p className="slsg-login-error" role="alert">
                {error}
              </p>
            ) : null}
            <button
              className="slsg-google-login"
              disabled={isGoogleSigningIn}
              onClick={handleGoogleSignIn}
              type="button"
            >
              <FcGoogle aria-hidden="true" size={18} />
              {isGoogleSigningIn ? "Google に接続しています..." : LOGIN_COPY.auth.googleLogin}
            </button>
            <div className="slsg-login-divider" />
            <p className="slsg-login-consent">
              続行すると、サービスのデータ取り扱いに同意したものとみなされます。{" "}
              <Link href="/privacy">プライバシーポリシー</Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
