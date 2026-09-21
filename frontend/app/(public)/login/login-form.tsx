"use client"

import {
  type Auth,
  GoogleAuthProvider,
  inMemoryPersistence,
  setPersistence,
  signInWithPopup,
  signOut,
} from "firebase/auth"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { FcGoogle } from "react-icons/fc"
import { createSessionAction } from "@/app/actions/auth"
import { ThemeToggle } from "@/components/theme-toggle"
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
    <main className="min-h-screen bg-[var(--canvas)] md:grid md:h-screen md:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] md:overflow-hidden">
      <section className="relative flex min-h-full flex-col justify-center overflow-hidden bg-[var(--inverse-surface)] p-[clamp(36px,8vw,120px)] text-[var(--inverse-ink)] md:h-screen">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:32px_32px]"
        />
        <div className="relative inline-flex items-start justify-between border-b border-white/20 pb-5">
          <span className="display-heading text-[2rem] leading-none tracking-[-0.06em]">
            {LOGIN_COPY.appName}
          </span>
          <span aria-hidden="true" className="grid grid-cols-2 gap-1">
            <span className="size-2 bg-[var(--signal)]" />
            <span className="size-2 bg-[var(--accent)]" />
            <span className="col-start-2 size-2 bg-[var(--signal)]" />
          </span>
        </div>
        <p className="mono-label relative mt-16 text-[var(--signal-soft)]">
          Secure learning protocol
        </p>
        <h1 className="display-heading relative mt-5 max-w-[10ch] text-[clamp(2.8rem,6vw,5.4rem)] leading-[1.05]">
          {LOGIN_COPY.title}
        </h1>
        <p className="relative mt-[22px] max-w-[31rem] leading-[1.8] text-white/65">
          {LOGIN_COPY.description}
        </p>
        <div aria-hidden="true" className="relative mt-[58px] flex gap-1.5">
          <span className="h-2 w-12 bg-[var(--accent)]" />
          <span className="h-2 w-12 bg-white/20" />
          <span className="h-2 w-12 bg-white/20" />
        </div>
      </section>
      <section
        aria-labelledby="login-heading"
        className="relative md:flex md:h-screen md:items-center md:overflow-y-auto"
      >
        <ThemeToggle className="absolute top-2 right-5 z-10" showLabel />
        <div className="surface-panel signal-corner my-[50px] mx-auto w-[min(440px,calc(100%-48px))] rounded-2xl p-[clamp(28px,4vw,48px)]">
          <p className="mono-label mb-6 text-[var(--ink-soft)]">Identity check / 01</p>
          <h2 className="display-heading mt-2.5 mb-2 text-[2.25rem]" id="login-heading">
            {LOGIN_COPY.auth.title}
          </h2>
          <p className="leading-[1.65] text-[var(--ink-soft)]">{LOGIN_COPY.auth.description}</p>
          {error ? (
            <p className="mt-6 text-[0.86rem] font-bold text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}
          <button
            className="secondary-action mt-7 inline-flex min-h-[46px] w-full items-center justify-center gap-2 rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isGoogleSigningIn}
            onClick={handleGoogleSignIn}
            type="button"
          >
            <FcGoogle aria-hidden="true" size={18} />
            {isGoogleSigningIn ? "Google に接続しています..." : LOGIN_COPY.auth.googleLogin}
          </button>
          <p className="mt-6 text-center text-[0.78rem] leading-6 text-[var(--ink-soft)]">
            続行すると、サービスのデータ取り扱いに同意したものとみなされます。{" "}
            <Link
              className="font-bold text-[var(--signal)] underline underline-offset-4"
              href="/privacy"
            >
              プライバシーポリシー
            </Link>
          </p>
        </div>
      </section>
    </main>
  )
}
