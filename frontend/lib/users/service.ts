import "server-only"

import type { DecodedIdToken } from "firebase-admin/auth"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import { buildInitialUserDocument } from "@/lib/users/user-document"

export async function ensureUserDocumentService(identity: DecodedIdToken): Promise<void> {
  const firestore = getFirebaseAdminFirestore()
  const userReference = firestore.collection("users").doc(identity.uid)

  await firestore.runTransaction(async (transaction) => {
    const userSnapshot = await transaction.get(userReference)
    if (userSnapshot.exists) return

    transaction.create(userReference, buildInitialUserDocument(identity))
  })
}
