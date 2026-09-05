import "server-only"

import type { UsersDocument } from "@/types/firestore"

type UserIdentity = {
  uid: string
  name?: unknown
  picture?: unknown
}

export function buildInitialUserDocument(
  identity: UserIdentity,
  createdAt = new Date(),
): UsersDocument {
  return {
    id: identity.uid,
    name: typeof identity.name === "string" && identity.name.trim() ? identity.name : "ユーザー",
    bio: "",
    icon_url: typeof identity.picture === "string" ? identity.picture : "",
    theme: "light",
    own_machines: [],
    solved_machines: [],
    created_at: createdAt.toISOString(),
  }
}
