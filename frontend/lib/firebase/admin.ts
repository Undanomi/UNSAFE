import "server-only"

import { type App, cert, getApp, getApps, initializeApp } from "firebase-admin/app"
import { getAuth } from "firebase-admin/auth"
import { getFirestore } from "firebase-admin/firestore"

function getRequiredEnvironmentVariable(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`${name} is not configured.`)
  }
  return value
}

function getFirebaseAdminApp(): App {
  if (getApps().length > 0) return getApp()

  const projectId =
    process.env.FIREBASE_ADMIN_PROJECT_ID ??
    getRequiredEnvironmentVariable("NEXT_PUBLIC_FIREBASE_PROJECT_ID")
  const clientEmail = getRequiredEnvironmentVariable("FIREBASE_ADMIN_CLIENT_EMAIL")
  const privateKey = getRequiredEnvironmentVariable("FIREBASE_ADMIN_PRIVATE_KEY").replace(
    /\\n/g,
    "\n",
  )

  return initializeApp({
    credential: cert({ clientEmail, privateKey, projectId }),
    projectId,
  })
}

export function getFirebaseAdminAuth() {
  return getAuth(getFirebaseAdminApp())
}

export function getFirebaseAdminFirestore() {
  return getFirestore(getFirebaseAdminApp())
}
