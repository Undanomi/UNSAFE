import "server-only"

import type { UserRecord } from "@/types/postgres"

export type UserIdentity = {
  uid: string
  name?: unknown
  picture?: unknown
}

export function buildInitialUserDocument(
  identity: UserIdentity,
  createdAt = new Date(),
): UserRecord {
  return {
    id: identity.uid,
    name: typeof identity.name === "string" && identity.name.trim() ? identity.name : "ユーザー",
    bio: "",
    icon_url: typeof identity.picture === "string" ? identity.picture : "",
    theme: "light",
    created_at: createdAt,
    updated_at: createdAt,
    profile_completed: false,
  }
}
