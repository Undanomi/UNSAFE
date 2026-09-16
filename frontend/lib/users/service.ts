import "server-only"

import type { DecodedIdToken } from "firebase-admin/auth"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import { buildInitialUserDocument } from "@/lib/users/user-document"
import type { UsersDocument } from "@/types/firestore"

export type UserProfileUpdate = Partial<
  Pick<UsersDocument, "bio" | "icon_url" | "name" | "profile_completed">
>

export async function ensureUserDocumentService(identity: DecodedIdToken): Promise<void> {
  const firestore = getFirebaseAdminFirestore()
  const userReference = firestore.collection("users").doc(identity.uid)

  await firestore.runTransaction(async (transaction) => {
    const userSnapshot = await transaction.get(userReference)
    if (userSnapshot.exists) return

    transaction.create(userReference, buildInitialUserDocument(identity))
  })
}

export async function getUserDocumentService(uid: string): Promise<UsersDocument | null> {
  const userSnapshot = await getFirebaseAdminFirestore().collection("users").doc(uid).get()

  if (!userSnapshot.exists) return null
  return userSnapshot.data() as UsersDocument
}

export async function updateUserProfileService(
  uid: string,
  profile: UserProfileUpdate,
): Promise<void> {
  await getFirebaseAdminFirestore().collection("users").doc(uid).update(profile)
}
