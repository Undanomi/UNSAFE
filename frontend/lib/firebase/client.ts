import { getApp, getApps, initializeApp } from "firebase/app"
import { type Auth, getAuth } from "firebase/auth"

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
}

function getAppInstance() {
  return getApps().length ? getApp() : initializeApp(config)
}

export function getFirebaseAuth(): Auth {
  if (typeof window === "undefined") {
    throw new Error("Firebase Authentication must be initialized in the browser.")
  }

  return getAuth(getAppInstance())
}
