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

      router.replace("/machines")
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
    <main className="min-h-screen bg-white md:grid md:h-screen md:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] md:overflow-hidden">
      <section className="flex min-h-full flex-col justify-center overflow-hidden bg-[#20201e] p-[clamp(36px,8vw,120px)] text-[#faf9f4] md:h-screen">
        <div className="inline-flex items-center gap-2.5 text-[1.45rem] font-extrabold tracking-[-0.06em]">
          <span className="grid size-[34px] place-items-center rounded-xl bg-white text-[1rem] tracking-normal text-[#20201e]">
            S
          </span>
          <span>{LOGIN_COPY.appName}</span>
        </div>
        <h1 className="mt-[78px] max-w-[9ch] text-[clamp(2.8rem,6vw,5.4rem)] leading-[1.05] font-bold tracking-[-0.035em]">
          {LOGIN_COPY.title}
        </h1>
        <p className="mt-[22px] max-w-[31rem] leading-[1.8] text-[#cbc9c2]">
          {LOGIN_COPY.description}
        </p>
        <div aria-hidden="true" className="mt-[58px] flex gap-2.5">
          <span className="h-2 w-[62px] rounded-full bg-white" />
          <span className="h-2 w-[62px] rounded-full bg-[#46443e]" />
          <span className="h-2 w-[62px] rounded-full bg-[#46443e]" />
        </div>
      </section>
      <section
        aria-labelledby="login-heading"
        className="md:flex md:h-screen md:items-center md:overflow-y-auto"
      >
        <div className="my-[50px] mx-auto w-[min(440px,calc(100%-48px))] rounded-3xl border border-[#e5e5e2] bg-white p-[clamp(28px,4vw,48px)] shadow-sm">
          <h2
            className="mt-2.5 mb-1.5 text-[2rem] font-bold tracking-[-0.035em]"
            id="login-heading"
          >
            {LOGIN_COPY.auth.title}
          </h2>
          <p className="leading-[1.65] text-[#61605b]">{LOGIN_COPY.auth.description}</p>
          {error ? (
            <p className="mt-6 text-[0.86rem] font-bold text-[#b14334]" role="alert">
              {error}
            </p>
          ) : null}
          <button
            className="mt-7 inline-flex min-h-[46px] w-full items-center justify-center gap-2 rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold text-[#20201e] shadow-sm transition hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isGoogleSigningIn}
            onClick={handleGoogleSignIn}
            type="button"
          >
            <FcGoogle aria-hidden="true" size={18} />
            {isGoogleSigningIn ? "Google に接続しています..." : LOGIN_COPY.auth.googleLogin}
          </button>
          <p className="mt-6 text-center text-[0.78rem] leading-6 text-[#61605b]">
            続行すると、サービスのデータ取り扱いに同意したものとみなされます。{" "}
            <Link className="font-bold text-[#20201e] underline underline-offset-4" href="/privacy">
              プライバシーポリシー
            </Link>
          </p>
        </div>
      </section>
    </main>
  )
}
