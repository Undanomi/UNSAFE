"use client"

import { ArrowLeft, ChevronDown, ChevronRight, Pencil } from "lucide-react"
import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { updateProfileAction } from "@/app/actions/profile"
import { TerminalTelemetry } from "@/components/terminal-telemetry"
import type { ProfileMachine, UserProfile } from "@/types/profile"

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
    <section className={`slsg-profile-page ${canEdit ? "is-own-profile" : "is-public-profile"}`}>
      <header className="slsg-profile-header">
        {showBackLink ? (
          <Link className="slsg-profile-back" href="/machines">
            <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
            マシン一覧へ戻る
          </Link>
        ) : null}
        {canEdit ? <p className="slsg-profile-kicker">アカウント</p> : null}
        <h1>プロフィール</h1>
        <p className="slsg-profile-description">アカウント情報の確認と管理を行います。</p>
      </header>

      <section
        className={`slsg-profile-hero ${isEditing ? "is-editing" : ""} ${canEdit ? "" : "is-public"}`}
      >
        {canEdit ? <ProfileCardGlow /> : null}
        <div className="slsg-profile-avatar-frame">
          <svg
            aria-hidden="true"
            className="slsg-profile-avatar-border"
            preserveAspectRatio="none"
            viewBox="0 0 100 100"
          >
            <defs>
              <clipPath id="slsg-profile-avatar-rounded-hex" clipPathUnits="objectBoundingBox">
                <path d="M.46.023 Q.5 0 .54.023 L.89.227 Q.93.25.93.3 L.93.7 Q.93.75.89.773 L.54.977 Q.5 1 .46.977 L.11.773 Q.07.75.07.7 L.07.3 Q.07.25.11.227 Z" />
              </clipPath>
              <linearGradient
                id="slsg-profile-avatar-border-base-gradient"
                gradientUnits="userSpaceOnUse"
                x1="0"
                x2="100"
                y1="0"
                y2="100"
              >
                <stop offset="0" stopColor="#c5f8ff" />
                <stop offset="0.3" stopColor="#78bfd5" />
                <stop offset="0.66" stopColor="#5698ff" />
                <stop offset="1" stopColor="#304e8e" stopOpacity="0.52" />
              </linearGradient>
              <linearGradient
                id="slsg-profile-avatar-glow-upper"
                gradientUnits="userSpaceOnUse"
                x1="46"
                x2="7"
                y1="2.3"
                y2="42"
              >
                <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                <stop offset="0.34" stopColor="#78bfd5" stopOpacity="0.42" />
                <stop offset="0.68" stopColor="#c5f8ff" />
                <stop offset="0.84" stopColor="#78bfd5" stopOpacity="0.34" />
                <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
              </linearGradient>
              <linearGradient
                id="slsg-profile-avatar-glow-lower"
                gradientUnits="userSpaceOnUse"
                x1="93"
                x2="54"
                y1="58"
                y2="97.7"
              >
                <stop offset="0" stopColor="#78bfd5" stopOpacity="0" />
                <stop offset="0.16" stopColor="#78bfd5" stopOpacity="0.38" />
                <stop offset="0.32" stopColor="#c5f8ff" />
                <stop offset="0.62" stopColor="#78bfd5" stopOpacity="0.38" />
                <stop offset="1" stopColor="#78bfd5" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              className="slsg-profile-avatar-border-base"
              d="M46 2.3 Q50 0 54 2.3 L89 22.7 Q93 25 93 30 L93 70 Q93 75 89 77.3 L54 97.7 Q50 100 46 97.7 L11 77.3 Q7 75 7 70 L7 30 Q7 25 11 22.7 Z"
              stroke="url(#slsg-profile-avatar-border-base-gradient)"
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="slsg-profile-avatar-border-glow"
              d="M46 2.3 L11 22.7 Q7 25 7 30 L7 42"
              stroke="url(#slsg-profile-avatar-glow-upper)"
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="slsg-profile-avatar-border-glow"
              d="M93 58 L93 70 Q93 75 89 77.3 L54 97.7"
              stroke="url(#slsg-profile-avatar-glow-lower)"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div className="slsg-profile-avatar">
            {displayAvatarUrl ? (
              <Image
                alt={`${displayFields.name}のプロフィール画像`}
                fill
                className="size-full object-cover"
                sizes="136px"
                src={displayAvatarUrl}
                unoptimized
              />
            ) : (
              profileInitial
            )}
          </div>
        </div>
        <div className="slsg-profile-identity">
          {isEditing ? (
            <div className="slsg-profile-edit-form">
              <label className="slsg-profile-field">
                <span>ユーザー名</span>
                <input
                  className="slsg-input"
                  maxLength={30}
                  onChange={(event) =>
                    setDraftFields((current) => ({ ...current, name: event.target.value }))
                  }
                  value={draftFields.name}
                />
              </label>
              <fieldset className="slsg-profile-field">
                <legend>アイコンの表示</legend>
                <div className="slsg-profile-icon-options">
                  <label>
                    <input
                      checked={iconMode === "google"}
                      name="profile-icon-mode"
                      onChange={() => setIconMode("google")}
                      type="radio"
                    />
                    <span className="text-[0.82rem] font-bold">Googleアイコン</span>
                  </label>
                  <label>
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
              <label className="slsg-profile-field">
                <span>自己紹介</span>
                <textarea
                  className="slsg-input min-h-28 resize-y"
                  maxLength={500}
                  onChange={(event) =>
                    setDraftFields((current) => ({ ...current, bio: event.target.value }))
                  }
                  value={draftFields.bio}
                />
              </label>
              {saveError ? (
                <p className="slsg-profile-error" role="alert">
                  {saveError}
                </p>
              ) : null}
              <div className="slsg-profile-edit-actions">
                <button
                  className="slsg-button-primary px-6"
                  disabled={isSaving}
                  onClick={saveProfile}
                  type="button"
                >
                  {isSaving ? "保存しています…" : "保存する"}
                </button>
                <button
                  className="slsg-button-secondary px-6"
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
              <h2>{profileFields.name}</h2>
              <p>{profileFields.bio}</p>
            </>
          )}
        </div>
        {canEdit && !isEditing ? (
          <button
            aria-label="プロフィールを編集"
            className="slsg-profile-edit-button"
            onClick={startEditing}
            type="button"
          >
            <Pencil aria-hidden="true" size={22} strokeWidth={1.8} />
            プロフィールを編集
          </button>
        ) : null}
      </section>

      <div className="slsg-profile-history-grid">
        <MachineRecordList items={profile.createdMachines} kind="created" title="作成したマシン" />
        <MachineRecordList items={profile.solvedMachines} kind="solved" title="解いたマシン" />
      </div>

      <TerminalTelemetry />
    </section>
  )
}

type MachineRecordListProps = {
  items: ProfileMachine[]
  kind: "created" | "solved"
  title: string
}

function formatProfileDate(value: string) {
  return value.replaceAll("/", ".").replaceAll("-", ".")
}

function MachineRecordList({ items, kind, title }: MachineRecordListProps) {
  const description =
    kind === "created" ? "あなたが作成したマシンの一覧です。" : "あなたが解いたマシンの一覧です。"

  return (
    <section className={`slsg-profile-history-card is-${kind}`}>
      <ProfileCardGlow />
      <header className="slsg-profile-history-header">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className="slsg-profile-history-columns" aria-hidden="true">
        <span>マシン名</span>
        <span>{kind === "created" ? "作成日" : "解いた日"}</span>
      </div>
      <ul className="slsg-profile-history-list">
        {items.length > 0 ? (
          items.map((machine) => (
            <li key={machine.id}>
              <Link className="slsg-profile-machine-row" href={`/machines/${machine.id}`}>
                <span className="slsg-profile-machine-copy">
                  <strong>{machine.name}</strong>
                  <small>セキュリティ学習マシン</small>
                </span>
                <span aria-hidden="true" className="slsg-profile-status-hex is-green" />
                <time>
                  {formatProfileDate(
                    kind === "solved" && machine.solvedAt ? machine.solvedAt : machine.createdAt,
                  )}
                </time>
                <ChevronRight aria-hidden="true" size={21} strokeWidth={1.6} />
              </Link>
            </li>
          ))
        ) : (
          <li className="slsg-profile-history-empty">まだ記録はありません。</li>
        )}
      </ul>
      {kind === "solved" ? (
        <details className="slsg-profile-exercise-log">
          <summary>
            <span>演習ログ</span>
            <ChevronDown aria-hidden="true" size={22} strokeWidth={1.6} />
          </summary>
          <div>
            {items.slice(0, 4).map((machine) => (
              <p key={machine.id}>
                {formatProfileDate(machine.solvedAt || machine.createdAt)} — {machine.name} を完了
              </p>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  )
}

function ProfileCardGlow() {
  return (
    <div aria-hidden="true" className="slsg-profile-card-glow">
      <span className="slsg-profile-card-glow-top" />
      <span className="slsg-profile-card-glow-right" />
      <span className="slsg-profile-card-glow-bottom" />
      <span className="slsg-profile-card-glow-left" />
    </div>
  )
}
