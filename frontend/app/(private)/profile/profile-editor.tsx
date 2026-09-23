"use client"

import { ArrowLeft, Pencil } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { updateProfileAction } from "@/app/actions/profile"
import type { ProfileMachine, UserProfile } from "@/stores/profile"

type ProfileEditorProps = {
  profile: UserProfile
  canEdit?: boolean
  showBackLink?: boolean
}

export function ProfileEditor({
  profile,
  canEdit = true,
  showBackLink = true,
}: ProfileEditorProps) {
  const router = useRouter()
  const [isEditing, setIsEditing] = useState(false)
  const [profileFields, setProfileFields] = useState(() => ({
    avatarUrl: profile.avatarUrl ?? "",
    bio: profile.bio,
    name: profile.name,
  }))
  const [draftFields, setDraftFields] = useState(profileFields)
  const [iconMode, setIconMode] = useState<"google" | "initial">(
    profileFields.avatarUrl ? "google" : "initial",
  )
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState("")

  const displayFields = isEditing ? draftFields : profileFields
  const displayAvatarUrl = isEditing && iconMode === "initial" ? "" : displayFields.avatarUrl
  const profileInitial = displayFields.name.trim().charAt(0).toUpperCase() || profile.initial

  function startEditing() {
    setDraftFields(profileFields)
    setIconMode(profileFields.avatarUrl ? "google" : "initial")
    setSaveError("")
    setIsEditing(true)
  }

  async function saveProfile() {
    if (isSaving) return

    setSaveError("")
    setIsSaving(true)

    try {
      const formData = new FormData()
      formData.set("name", draftFields.name)
      formData.set("bio", draftFields.bio)
      formData.set("icon_mode", iconMode)

      const result = await updateProfileAction(formData)

      if (!result.success) {
        setSaveError(result.message)
        return
      }

      const updatedFields = {
        ...profileFields,
        avatarUrl: result.profile.iconUrl,
        name: result.profile.name,
        bio: result.profile.bio,
      }
      setProfileFields(updatedFields)
      setDraftFields(updatedFields)
      setIconMode(updatedFields.avatarUrl ? "google" : "initial")
      setIsEditing(false)
      router.refresh()
    } catch {
      setSaveError("プロフィールを保存できませんでした。もう一度お試しください。")
    } finally {
      setIsSaving(false)
    }
  }

  function cancelEditing() {
    setSaveError("")
    setDraftFields(profileFields)
    setIconMode(profileFields.avatarUrl ? "google" : "initial")
    setIsEditing(false)
  }

  return (
    <section className="grid gap-7">
      <div>
        {showBackLink ? (
          <Link
            className="inline-flex items-center gap-2 text-[0.86rem] font-bold text-[#61605b] transition hover:text-[#20201e]"
            href="/machines"
          >
            <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
            マシン一覧へ戻る
          </Link>
        ) : null}
        <h1
          className={`${showBackLink ? "mt-5" : ""} text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.05] font-bold tracking-[-0.035em]`}
        >
          ユーザー情報
        </h1>
        <p className="mt-2 leading-[1.65] text-[#61605b]">
          プロフィールと、これまでの学習記録を確認できます。
        </p>
      </div>

      <section className="relative flex items-start gap-6 rounded-3xl border border-[#e5e5e2] bg-white p-7 shadow-sm max-sm:flex-col">
        <div className="relative grid size-20 shrink-0 place-items-center overflow-hidden rounded-full bg-[#20201e] text-2xl font-bold text-white">
          {displayAvatarUrl ? (
            <Image
              alt={`${displayFields.name}のプロフィール画像`}
              fill
              className="size-full object-cover"
              sizes="80px"
              src={displayAvatarUrl}
              unoptimized
            />
          ) : (
            profileInitial
          )}
        </div>
        <div className="min-w-0 flex-1 pr-12">
          {isEditing ? (
            <div className="grid gap-3">
              <label className="grid gap-2 text-[0.86rem] font-extrabold">
                <span>ユーザー名</span>
                <input
                  className="w-full rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
                  maxLength={30}
                  onChange={(event) =>
                    setDraftFields((current) => ({ ...current, name: event.target.value }))
                  }
                  value={draftFields.name}
                />
              </label>
              <fieldset className="grid gap-2">
                <legend className="text-[0.86rem] font-extrabold">アイコンの表示</legend>
                <div className="flex flex-wrap gap-3">
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#d6d6d2] px-4 py-3 has-checked:border-[#20201e] has-checked:bg-[#f4f4f1]">
                    <input
                      checked={iconMode === "google"}
                      name="profile-icon-mode"
                      onChange={() => setIconMode("google")}
                      type="radio"
                    />
                    <span className="text-[0.82rem] font-bold">Googleアイコン</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-[#d6d6d2] px-4 py-3 has-checked:border-[#20201e] has-checked:bg-[#f4f4f1]">
                    <input
                      checked={iconMode === "initial"}
                      name="profile-icon-mode"
                      onChange={() => setIconMode("initial")}
                      type="radio"
                    />
                    <span className="text-[0.82rem] font-bold">イニシャル</span>
                  </label>
                </div>
              </fieldset>
              <label className="grid gap-2 text-[0.86rem] font-extrabold">
                <span>自己紹介</span>
                <textarea
                  className="min-h-28 w-full resize-y rounded-[14px] border border-[#d6d6d2] bg-white px-[14px] py-[13px] text-[#20201e] outline-none focus:border-[#20201e] focus:ring-3 focus:ring-[#20201e]/15"
                  maxLength={500}
                  onChange={(event) =>
                    setDraftFields((current) => ({ ...current, bio: event.target.value }))
                  }
                  value={draftFields.bio}
                />
              </label>
              {saveError ? (
                <p className="text-[0.86rem] font-bold text-[#b14334]" role="alert">
                  {saveError}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <button
                  className="inline-flex min-h-[46px] items-center justify-center rounded-[15px] border border-transparent bg-[#20201e] px-[18px] text-[0.92rem] font-extrabold text-white shadow-sm transition hover:-translate-y-px hover:bg-[#3a3a37] disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={isSaving}
                  onClick={saveProfile}
                  type="button"
                >
                  {isSaving ? "保存しています…" : "保存する"}
                </button>
                <button
                  className="inline-flex min-h-[46px] items-center justify-center rounded-[15px] border border-transparent bg-transparent px-[18px] text-[0.92rem] font-extrabold text-[#61605b] hover:bg-[#f5f5f3]"
                  disabled={isSaving}
                  onClick={cancelEditing}
                  type="button"
                >
                  取り消す
                </button>
              </div>
            </div>
          ) : (
            <>
              <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
                {profileFields.name}
              </h2>
              <p className="mt-2 leading-[1.65] text-[#61605b]">{profileFields.bio}</p>
            </>
          )}
        </div>
        {canEdit && !isEditing ? (
          <button
            aria-label="プロフィールを編集"
            className="absolute top-6 right-6 inline-flex size-10 items-center justify-center rounded-xl border border-[#d6d6d2] bg-white text-[#20201e] shadow-sm transition hover:-translate-y-px hover:bg-[#f8f8f7]"
            onClick={startEditing}
            type="button"
          >
            <Pencil aria-hidden="true" size={17} strokeWidth={2} />
          </button>
        ) : null}
      </section>

      <div className="grid grid-cols-2 gap-6 max-md:grid-cols-1">
        <MachineRecordList items={profile.createdMachines} title="作成したマシン" />
        <MachineRecordList items={profile.solvedMachines} title="解いたマシン" />
      </div>
    </section>
  )
}

type MachineRecordListProps = {
  items: ProfileMachine[]
  title: string
}

function MachineRecordList({ items, title }: MachineRecordListProps) {
  return (
    <section className="flex h-80 flex-col rounded-3xl border border-[#e5e5e2] bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
          {title}
        </h2>
        <span className="grid min-w-7 place-items-center rounded-full bg-[#20201e] px-2 py-1 text-[0.75rem] font-bold text-white">
          {items.length}
        </span>
      </div>
      <ul className="mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-2">
        {items.length > 0 ? (
          items.map((machine) => (
            <li className="border-t border-[#e5e5e2] first:border-t-0" key={machine.id}>
              <Link className="grid gap-1 py-3 hover:underline" href={`/machines/${machine.id}`}>
                <span>{machine.name}</span>
                <small className="text-[0.75rem] text-[#61605b]">
                  作成 {machine.createdAt}
                  {"solvedAt" in machine && machine.solvedAt ? ` · 解答 ${machine.solvedAt}` : ""}
                </small>
              </Link>
            </li>
          ))
        ) : (
          <li className="py-3 text-[0.86rem] text-[#61605b]">まだ記録はありません。</li>
        )}
      </ul>
    </section>
  )
}
