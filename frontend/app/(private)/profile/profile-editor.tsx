"use client"

import { ArrowLeft, Pencil } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { updateProfileAction } from "@/app/actions/profile"
import { PROFILE_DATA, type ProfileMachine, type UserProfile } from "@/stores/profile"

type ProfileEditorProps = {
  profile?: UserProfile
  canEdit?: boolean
  showBackLink?: boolean
}

export function ProfileEditor({
  profile = PROFILE_DATA,
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
            className="inline-flex items-center gap-2 text-[0.86rem] font-bold text-[var(--ink-soft)] transition hover:text-[var(--signal)]"
            href="/machines"
          >
            <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
            マシン一覧へ戻る
          </Link>
        ) : null}
        <h1
          className={`${showBackLink ? "mt-5" : ""} display-heading text-[clamp(1.75rem,3vw,2.75rem)] leading-[1.05]`}
        >
          ユーザー情報
        </h1>
        <p className="mt-2 leading-[1.65] text-[var(--ink-soft)]">
          プロフィールと、これまでの学習記録を確認できます。
        </p>
      </div>

      <section className="surface-panel signal-corner relative flex items-start gap-6 rounded-2xl p-7 max-sm:flex-col">
        <div className="relative grid size-20 shrink-0 place-items-center overflow-hidden rounded-full bg-[var(--inverse-surface)] text-2xl font-bold text-[var(--inverse-ink)]">
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
                  className="field-control w-full rounded-lg px-[14px] py-[13px]"
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
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--line)] px-4 py-3 has-checked:border-[var(--signal)] has-checked:bg-[var(--signal-soft)]">
                    <input
                      checked={iconMode === "google"}
                      name="profile-icon-mode"
                      onChange={() => setIconMode("google")}
                      type="radio"
                    />
                    <span className="text-[0.82rem] font-bold">Googleアイコン</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--line)] px-4 py-3 has-checked:border-[var(--signal)] has-checked:bg-[var(--signal-soft)]">
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
                  className="field-control min-h-28 w-full resize-y rounded-lg px-[14px] py-[13px]"
                  maxLength={500}
                  onChange={(event) =>
                    setDraftFields((current) => ({ ...current, bio: event.target.value }))
                  }
                  value={draftFields.bio}
                />
              </label>
              {saveError ? (
                <p className="text-[0.86rem] font-bold text-[var(--danger)]" role="alert">
                  {saveError}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <button
                  className="primary-action inline-flex min-h-[46px] items-center justify-center rounded-lg px-[18px] text-[0.9rem] font-bold disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={isSaving}
                  onClick={saveProfile}
                  type="button"
                >
                  {isSaving ? "保存しています…" : "保存する"}
                </button>
                <button
                  className="inline-flex min-h-[46px] items-center justify-center rounded-lg px-[18px] text-[0.9rem] font-bold text-[var(--ink-soft)] hover:bg-[var(--surface-muted)]"
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
              <p className="mt-2 leading-[1.65] text-[var(--ink-soft)]">{profileFields.bio}</p>
            </>
          )}
        </div>
        {canEdit && !isEditing ? (
          <button
            aria-label="プロフィールを編集"
            className="secondary-action absolute top-6 right-6 inline-flex size-10 items-center justify-center rounded-lg"
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
    <section className="surface-panel flex h-80 flex-col rounded-2xl p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-[clamp(1.15rem,1.6vw,1.5rem)] font-bold tracking-[-0.035em]">
          {title}
        </h2>
        <span className="pixel-index grid min-w-7 place-items-center rounded-md bg-[var(--signal-soft)] px-2 py-1 text-[0.75rem]">
          {items.length}
        </span>
      </div>
      <ul className="mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-2">
        {items.length > 0 ? (
          items.map((machine) => (
            <li className="border-t border-[var(--line)] first:border-t-0" key={machine.id}>
              <Link className="grid gap-1 py-3 hover:underline" href={`/machines/${machine.id}`}>
                <span>{machine.name}</span>
                <small className="font-mono text-[0.72rem] text-[var(--ink-soft)]">
                  作成 {machine.createdAt}
                  {"solvedAt" in machine && machine.solvedAt ? ` · 解答 ${machine.solvedAt}` : ""}
                </small>
              </Link>
            </li>
          ))
        ) : (
          <li className="py-3 text-[0.86rem] text-[var(--ink-soft)]">まだ記録はありません。</li>
        )}
      </ul>
    </section>
  )
}
