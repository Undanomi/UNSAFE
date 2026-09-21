"use client"

import Image from "next/image"
import { useRouter } from "next/navigation"
import { type FormEvent, useState } from "react"
import { logoutAction } from "@/app/actions/auth"
import { completeProfileAction } from "@/app/actions/profile"
import { ThemeToggle } from "@/components/theme-toggle"

type ProfileSetupFormProps = {
  initialName: string
  initialIconUrl: string
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

  return (
    <main className="relative min-h-screen bg-[var(--canvas)] px-6 py-12">
      <ThemeToggle className="absolute top-2 right-6 z-10" showLabel />
      <div className="surface-panel mx-auto grid w-full max-w-[960px] overflow-hidden rounded-2xl md:grid-cols-[0.8fr_1.2fr]">
        <section className="relative flex flex-col justify-between overflow-hidden bg-[var(--inverse-surface)] p-10 text-[var(--inverse-ink)]">
          <div
            aria-hidden="true"
            className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:32px_32px]"
          />
          <div>
            <div className="display-heading relative text-[1.8rem] tracking-[-0.06em]">SLSG</div>
            <p className="mono-label relative mt-16 text-[var(--signal-soft)]">STEP 1 / 1</p>
            <h1 className="display-heading relative mt-4 text-[clamp(2rem,4vw,3.3rem)] leading-[1.08]">
              あなたらしいプロフィールを作りましょう。
            </h1>
          </div>
          <div className="mt-12 grid gap-5">
            <p className="relative text-sm leading-7 text-white/65">
              名前とアイコンの表示方法は、あとからユーザー情報画面で変更できます。
            </p>
            <form action={logoutAction}>
              <button
                className="relative text-sm font-bold text-white/65 underline decoration-white/30 underline-offset-4 transition hover:text-white"
                type="submit"
              >
                別のGoogleアカウントでログイン
              </button>
            </form>
          </div>
        </section>

        <form
          className="grid content-center gap-7 p-[clamp(32px,6vw,72px)]"
          onSubmit={submitProfile}
        >
          <div>
            <p className="mono-label mb-2 text-[var(--ink-soft)]">Identity setup</p>
            <h2 className="display-heading text-3xl">プロフィール登録</h2>
            <p className="mt-2 leading-7 text-[var(--ink-soft)]">
              他のユーザーに表示される名前を設定します。
            </p>
          </div>

          <div className="flex items-center gap-5">
            <div className="relative grid size-24 shrink-0 place-items-center overflow-hidden rounded-full bg-[var(--inverse-surface)] text-3xl font-bold text-[var(--inverse-ink)]">
              {iconMode === "google" && initialIconUrl ? (
                <Image
                  alt={`${name || "ユーザー"}のGoogleプロフィール画像`}
                  fill
                  className="object-cover"
                  sizes="96px"
                  src={initialIconUrl}
                  unoptimized
                />
              ) : (
                initial
              )}
            </div>
            <p className="text-sm leading-6 text-[var(--ink-soft)]">
              {iconMode === "google"
                ? "Googleアカウントのアイコンを表示します。"
                : "画像を使わず、名前のイニシャルを表示します。"}
            </p>
          </div>

          <fieldset className="grid gap-3">
            <legend className="text-sm font-extrabold">アイコンの表示</legend>
            <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-[var(--line)] p-4 has-checked:border-[var(--signal)] has-checked:bg-[var(--signal-soft)] has-disabled:cursor-not-allowed has-disabled:opacity-45">
                <input
                  checked={iconMode === "google"}
                  disabled={!initialIconUrl}
                  name="icon-mode"
                  onChange={() => setIconMode("google")}
                  type="radio"
                />
                <span className="text-sm font-bold">Googleアイコン</span>
              </label>
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-[var(--line)] p-4 has-checked:border-[var(--signal)] has-checked:bg-[var(--signal-soft)]">
                <input
                  checked={iconMode === "initial"}
                  name="icon-mode"
                  onChange={() => setIconMode("initial")}
                  type="radio"
                />
                <span className="text-sm font-bold">イニシャル</span>
              </label>
            </div>
          </fieldset>

          <label className="grid gap-2 text-sm font-extrabold">
            <span>ユーザー名</span>
            <input
              autoComplete="nickname"
              className="field-control w-full rounded-lg px-[14px] py-[13px]"
              maxLength={30}
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
            <span className="text-right font-mono text-xs font-normal text-[var(--ink-soft)]">
              {name.length}/30
            </span>
          </label>

          {error ? (
            <p className="text-sm font-bold text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}

          <button
            className="primary-action inline-flex min-h-[50px] items-center justify-center rounded-lg px-5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isSaving}
            type="submit"
          >
            {isSaving ? "登録しています…" : "このプロフィールではじめる"}
          </button>
        </form>
      </div>
    </main>
  )
}
