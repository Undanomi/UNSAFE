import "server-only"

import { queryDatabase } from "@/lib/database/client"
import { buildInitialUserDocument, type UserIdentity } from "@/lib/users/user-document"
import type { UserProfile } from "@/stores/profile"
import type { UserRecord } from "@/types/postgres"

export type UserProfileUpdate = Partial<
  Pick<UserRecord, "bio" | "icon_url" | "name" | "profile_completed">
>

type ProfileMachineRow = {
  id: string
  name: string
  created_at: Date
}

type SolvedProfileMachineRow = ProfileMachineRow & {
  solved_at: Date
}

function formatProfileDate(value: Date): string {
  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeZone: "Asia/Tokyo",
  }).format(value)
}

export async function ensureUserDocumentService(identity: UserIdentity): Promise<void> {
  const user = buildInitialUserDocument(identity)
  await queryDatabase(
    `INSERT INTO users
      (id, name, bio, icon_url, theme, profile_completed, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     ON CONFLICT (id) DO NOTHING`,
    [
      user.id,
      user.name,
      user.bio,
      user.icon_url,
      user.theme,
      user.profile_completed,
      user.created_at,
      user.updated_at,
    ],
  )
}

export async function getUserDocumentService(uid: string): Promise<UserRecord | null> {
  const result = await queryDatabase<UserRecord>("SELECT * FROM users WHERE id = $1", [uid])
  return result.rows[0] ?? null
}

export async function getUserProfileService(
  viewerUserId: string,
  targetUserId: string,
): Promise<UserProfile | null> {
  const user = await getUserDocumentService(targetUserId)

  if (!user) return null

  const createdResult = await queryDatabase<ProfileMachineRow>(
    `SELECT
       m.id,
       m.name,
       m.created_at
     FROM machines m
     WHERE m.created_by = $2
       AND m.status <> 'deleted'
       AND (
         m.published = true
         OR m.created_by = $1
       )
     ORDER BY m.created_at DESC, m.id ASC`,
    [viewerUserId, targetUserId],
  )

  const solvedResult = await queryDatabase<SolvedProfileMachineRow>(
    `SELECT
       m.id,
       m.name,
       m.created_at,
       s.solved_at
     FROM machine_solutions s
     JOIN machines m
       ON m.id = s.machine_id
     WHERE s.user_id = $2
       AND m.status <> 'deleted'
       AND (
         m.published = true
         OR m.created_by = $1
       )
     ORDER BY s.solved_at DESC, m.id ASC`,
    [viewerUserId, targetUserId],
  )

  return {
    id: user.id,
    name: user.name,
    initial: user.name.trim().charAt(0).toUpperCase() || "U",
    bio: user.bio,
    avatarUrl: user.icon_url,
    createdMachines: createdResult.rows.map((machine) => ({
      id: machine.id,
      name: machine.name,
      createdAt: formatProfileDate(machine.created_at),
    })),
    solvedMachines: solvedResult.rows.map((machine) => ({
      id: machine.id,
      name: machine.name,
      createdAt: formatProfileDate(machine.created_at),
      solvedAt: formatProfileDate(machine.solved_at),
    })),
  }
}

export async function getOrCreateUserDocumentService(identity: UserIdentity): Promise<UserRecord> {
  const existingDocument = await getUserDocumentService(identity.uid)
  if (existingDocument) return existingDocument

  await ensureUserDocumentService(identity)
  const createdDocument = await getUserDocumentService(identity.uid)
  if (!createdDocument) throw new Error("User document could not be created.")

  return createdDocument
}

export async function updateUserProfileService(
  uid: string,
  profile: UserProfileUpdate,
): Promise<void> {
  const result = await queryDatabase(
    `UPDATE users SET
       name = COALESCE($2, name),
       bio = COALESCE($3, bio),
       icon_url = COALESCE($4, icon_url),
       profile_completed = COALESCE($5, profile_completed),
       updated_at = now()
     WHERE id = $1`,
    [
      uid,
      profile.name ?? null,
      profile.bio ?? null,
      profile.icon_url ?? null,
      profile.profile_completed ?? null,
    ],
  )
  if (result.rowCount === 0) throw new Error("User was not found.")
}
