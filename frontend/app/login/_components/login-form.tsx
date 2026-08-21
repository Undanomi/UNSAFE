"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { FcGoogle } from "react-icons/fc"
import { loginCopy } from "@/stores/login"

type AuthMode = "login" | "register"

export function LoginForm() {
  const router = useRouter()
  const [authMode, setAuthMode] = useState<AuthMode>("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const isRegistering = authMode === "register"
  const authCopy = loginCopy.auth[authMode]

  function switchAuthMode() {
    setAuthMode((mode) => (mode === "login" ? "register" : "login"))
    setError("")
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!email.trim() || !password) {
      setError("メールアドレスとパスワードを入力してください。")
      return
    }
    setError("")
    router.push("/machines")
  }

  return (
    <main className="min-h-screen bg-white md:grid md:h-screen md:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] md:overflow-hidden">
      <section className="flex min-h-full flex-col justify-center overflow-hidden bg-[#20201e] p-[clamp(36px,8vw,120px)] text-[#faf9f4] md:h-screen">
        <div className="inline-flex items-center gap-2.5 text-[1.45rem] font-extrabold tracking-[-0.06em]">
          <span className="grid size-[34px] place-items-center rounded-xl bg-white text-[1rem] tracking-normal text-[#20201e]">
            S
          </span>
          <span>{loginCopy.appName}</span>
        </div>
        <h1 className="mt-[78px] max-w-[9ch] text-[clamp(2.8rem,6vw,5.4rem)] leading-[1.05] font-bold tracking-[-0.035em]">
          {loginCopy.title}
        </h1>
        <p className="mt-[22px] max-w-[31rem] leading-[1.8] text-[#cbc9c2]">
          {loginCopy.description}
        </p>
        <div aria-hidden="true" className="mt-[58px] flex gap-2.5">
          <span className="h-2 w-[62px] rounded-full bg-white" />
          <span className="h-2 w-[62px] rounded-full bg-[#46443e]" />
          <span className="h-2 w-[62px] rounded-full bg-[#46443e]" />
        </div>
      </section>
      <section aria-labelledby="login-heading" className="md:h-screen md:overflow-y-auto">
        <div className="my-[50px] mx-auto w-[min(440px,calc(100%-48px))] rounded-3xl border border-[#e5e5e2] bg-white p-[clamp(28px,4vw,48px)] shadow-sm">
          <h2
            className="mt-2.5 mb-1.5 text-[2rem] font-bold tracking-[-0.035em]"
            id="login-heading"
          >
            {authCopy.title}
          </h2>
          <p className="leading-[1.65] text-[#61605b]">{authCopy.description}</p>
          <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[0.82rem] text-[#61605b]">
            <span>
              {isRegistering
                ? loginCopy.auth.switch.loginPrompt
                : loginCopy.auth.switch.registerPrompt}
            </span>
            <button
              className="border-b border-current bg-transparent p-0 text-[inherit] font-extrabold text-[#20201e] hover:text-[#61605b]"
              onClick={switchAuthMode}
              type="button"
            >
              {isRegistering ? loginCopy.auth.switch.login : loginCopy.auth.switch.register}
            </button>
          </div>
          <form className="mt-7 grid gap-5" onSubmit={handleSubmit}>
            <label className="grid gap-2 text-[0.86rem] font-extrabold">
              <span>メールアドレス</span>
              <input
                autoComplete="email"
                className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none placeholder:text-[#8a8984] focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="tanaka@example.com"
                type="email"
                value={email}
              />
            </label>
            <label className="grid gap-2 text-[0.86rem] font-extrabold">
              <span>パスワード</span>
              <input
                autoComplete={isRegistering ? "new-password" : "current-password"}
                className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none placeholder:text-[#8a8984] focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                type="password"
                value={password}
              />
            </label>
            {error ? <p className="text-[0.86rem] font-bold text-[#b14334]">{error}</p> : null}
            <button
              className="inline-flex min-h-[46px] w-full items-center justify-center gap-2 rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
              type="submit"
            >
              {authCopy.submit}
            </button>
          </form>
          <div className="my-6 flex items-center gap-3 text-center text-[0.8rem] text-[#61605b] before:h-px before:flex-1 before:bg-[#d6d6d2] after:h-px after:flex-1 after:bg-[#d6d6d2]">
            <span>または</span>
          </div>
          <button
            className="inline-flex min-h-[46px] w-full items-center justify-center gap-2 rounded-[15px] border border-[#d6d6d2] bg-white px-[18px] text-[0.92rem] font-extrabold text-[#20201e] shadow-sm transition hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-55"
            onClick={() => router.push("/machines")}
            type="button"
          >
            <FcGoogle aria-hidden="true" size={18} />
            {isRegistering ? loginCopy.auth.googleRegistration : loginCopy.auth.googleLogin}
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
