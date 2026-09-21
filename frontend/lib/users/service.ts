import "server-only"

import { queryDatabase } from "@/lib/database/client"
import { buildInitialUserDocument, type UserIdentity } from "@/lib/users/user-document"
import type { UserRecord } from "@/types/postgres"

export type UserProfileUpdate = Partial<
  Pick<UserRecord, "bio" | "icon_url" | "name" | "profile_completed">
>

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
