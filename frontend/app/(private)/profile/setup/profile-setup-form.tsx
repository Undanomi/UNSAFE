"use client"

import Image from "next/image"
import { useRouter } from "next/navigation"
import { type FormEvent, useState } from "react"
import { logoutAction } from "@/app/actions/auth"
import { completeProfileAction } from "@/app/actions/profile"

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
    <main className="min-h-screen bg-[#f7f7f5] px-6 py-12">
      <div className="mx-auto grid w-full max-w-[960px] overflow-hidden rounded-[32px] border border-[#deded9] bg-white shadow-sm md:grid-cols-[0.8fr_1.2fr]">
        <section className="flex flex-col justify-between bg-[#20201e] p-10 text-white">
          <div>
            <div className="inline-flex items-center gap-2.5 text-[1.35rem] font-extrabold tracking-[-0.06em]">
              <span className="grid size-[34px] place-items-center rounded-xl bg-white text-[1rem] tracking-normal text-[#20201e]">
                S
              </span>
              SLSG
            </div>
            <p className="mt-16 text-sm font-bold text-[#aaa9a3]">STEP 1 / 1</p>
            <h1 className="mt-4 text-[clamp(2rem,4vw,3.3rem)] leading-[1.08] font-bold tracking-[-0.045em]">
              あなたらしいプロフィールを作りましょう。
            </h1>
          </div>
          <div className="mt-12 grid gap-5">
            <p className="text-sm leading-7 text-[#cbc9c2]">
              名前とアイコンの表示方法は、あとからユーザー情報画面で変更できます。
            </p>
            <form action={logoutAction}>
              <button
                className="text-sm font-bold text-[#cbc9c2] underline decoration-[#77766f] underline-offset-4 transition hover:text-white"
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
            <h2 className="text-3xl font-bold tracking-[-0.035em]">プロフィール登録</h2>
            <p className="mt-2 leading-7 text-[#61605b]">
              他のユーザーに表示される名前を設定します。
            </p>
          </div>

          <div className="flex items-center gap-5">
            <div className="relative grid size-24 shrink-0 place-items-center overflow-hidden rounded-full bg-[#20201e] text-3xl font-bold text-white">
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
            <p className="text-sm leading-6 text-[#61605b]">
              {iconMode === "google"
                ? "Googleアカウントのアイコンを表示します。"
                : "画像を使わず、名前のイニシャルを表示します。"}
            </p>
          </div>

          <fieldset className="grid gap-3">
            <legend className="text-sm font-extrabold">アイコンの表示</legend>
            <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
              <label className="flex cursor-pointer items-center gap-3 rounded-[14px] border border-[#d6d6d2] p-4 has-checked:border-[#20201e] has-checked:bg-[#f4f4f1] has-disabled:cursor-not-allowed has-disabled:opacity-45">
                <input
                  checked={iconMode === "google"}
                  disabled={!initialIconUrl}
                  name="icon-mode"
                  onChange={() => setIconMode("google")}
                  type="radio"
                />
                <span className="text-sm font-bold">Googleアイコン</span>
              </label>
              <label className="flex cursor-pointer items-center gap-3 rounded-[14px] border border-[#d6d6d2] p-4 has-checked:border-[#20201e] has-checked:bg-[#f4f4f1]">
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
              className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
              maxLength={30}
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
            <span className="text-right text-xs font-normal text-[#74736e]">{name.length}/30</span>
          </label>

          {error ? (
            <p className="text-sm font-bold text-[#b14334]" role="alert">
              {error}
            </p>
          ) : null}

          <button
            className="inline-flex min-h-[50px] items-center justify-center rounded-[15px] bg-[#20201e] px-5 text-sm font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
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
