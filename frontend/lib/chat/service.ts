import "server-only"

import { Timestamp } from "firebase-admin/firestore"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import { BUILDING_MACHINE_DESCRIPTION } from "@/lib/machines/description"
import {
  CHAT_STEPS,
  type ChatAnswers,
  type ChatCreationStatus,
  type ChatSession,
  type ChatSessionSummary,
  EMPTY_CHAT_ANSWERS,
} from "@/stores/chat"

const CHAT_COLLECTION = "chat_sessions"
const MACHINE_COLLECTION = "machines"

type ChatSessionDocument = {
  ai_session_id: string
  owner_user_id: string
  name: string
  current_step: number
  basic_ready: boolean
  answers: ChatAnswers
  creation_status: ChatCreationStatus
  machine_id: string | null
  created_at: Timestamp
  updated_at: Timestamp
}

function toChatSession(id: string, document: ChatSessionDocument): ChatSession {
  return {
    id,
    name: document.name,
    status: document.basic_ready ? "基本設定完了" : "入力中",
    initialStep: document.current_step ?? CHAT_STEPS.machineName,
    initialAnswers: { ...EMPTY_CHAT_ANSWERS, ...document.answers },
    creationStatus: document.creation_status ?? "input",
    machineId: document.machine_id ?? null,
  }
}

function chatReference(sessionId: string) {
  return getFirebaseAdminFirestore().collection(CHAT_COLLECTION).doc(sessionId)
}

export async function createChatSessionService(
  ownerUserId: string,
  aiSessionId: string,
  answers: ChatAnswers,
  currentStep: number,
  basicReady: boolean,
): Promise<ChatSession> {
  const now = Timestamp.now()
  const document: ChatSessionDocument = {
    ai_session_id: aiSessionId,
    owner_user_id: ownerUserId,
    name: answers.name.trim(),
    current_step: currentStep,
    basic_ready: basicReady,
    answers,
    creation_status: "input",
    machine_id: null,
    created_at: now,
    updated_at: now,
  }

  await chatReference(aiSessionId).create(document)
  return toChatSession(aiSessionId, document)
}

export async function getChatSessionService(
  ownerUserId: string,
  sessionId: string,
): Promise<ChatSession | null> {
  const snapshot = await chatReference(sessionId).get()
  if (!snapshot.exists) return null

  const document = snapshot.data() as ChatSessionDocument
  if (document.owner_user_id !== ownerUserId) return null
  return toChatSession(snapshot.id, document)
}

export async function listChatSessionsService(ownerUserId: string): Promise<ChatSessionSummary[]> {
  const snapshot = await getFirebaseAdminFirestore()
    .collection(CHAT_COLLECTION)
    .where("owner_user_id", "==", ownerUserId)
    .get()

  return snapshot.docs
    .map((documentSnapshot) => {
      const document = documentSnapshot.data() as ChatSessionDocument
      return {
        session: toChatSession(documentSnapshot.id, document),
        updatedAt: document.updated_at?.toMillis() ?? 0,
      }
    })
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .map(({ session }) => ({ id: session.id, name: session.name, status: session.status }))
}

export async function saveChatProgressService(
  ownerUserId: string,
  sessionId: string,
  answers: ChatAnswers,
  currentStep: number,
  basicReady: boolean,
): Promise<ChatSession | null> {
  const reference = chatReference(sessionId)
  const firestore = getFirebaseAdminFirestore()

  return firestore.runTransaction(async (transaction) => {
    const snapshot = await transaction.get(reference)
    if (!snapshot.exists) return null

    const document = snapshot.data() as ChatSessionDocument
    if (document.owner_user_id !== ownerUserId) return null

    const updated: ChatSessionDocument = {
      ...document,
      name: answers.name.trim(),
      current_step: currentStep,
      basic_ready: basicReady,
      answers,
      updated_at: Timestamp.now(),
    }
    transaction.set(reference, updated)
    return toChatSession(sessionId, updated)
  })
}

export async function setChatCreationStatusService(
  ownerUserId: string,
  sessionId: string,
  creationStatus: ChatCreationStatus,
): Promise<boolean> {
  const reference = chatReference(sessionId)
  const firestore = getFirebaseAdminFirestore()

  return firestore.runTransaction(async (transaction) => {
    const snapshot = await transaction.get(reference)
    if (!snapshot.exists) return false
    const document = snapshot.data() as ChatSessionDocument
    if (document.owner_user_id !== ownerUserId) return false

    transaction.update(reference, {
      creation_status: creationStatus,
      error_message: null,
      updated_at: Timestamp.now(),
    })
    return true
  })
}

function difficultyToLevel(difficulty: ChatAnswers["difficulty"]) {
  if (difficulty === "Medium") return "medium"
  if (difficulty === "High") return "hard"
  return "easy"
}

export async function createMachineDocumentService(
  ownerUserId: string,
  sessionId: string,
  flags: { userFlag: string | null; systemFlag: string | null },
): Promise<string | null> {
  const firestore = getFirebaseAdminFirestore()
  const reference = chatReference(sessionId)

  return firestore.runTransaction(async (transaction) => {
    const snapshot = await transaction.get(reference)
    if (!snapshot.exists) return null
    const chat = snapshot.data() as ChatSessionDocument
    if (chat.owner_user_id !== ownerUserId) return null

    const userFlag = chat.answers.needsUserFlag ? flags.userFlag?.trim() : ""
    const systemFlag = chat.answers.needsSystemFlag ? flags.systemFlag?.trim() : ""
    if (chat.answers.needsUserFlag && !userFlag) {
      throw new Error("AI server did not return a user flag.")
    }
    if (chat.answers.needsSystemFlag && !systemFlag) {
      throw new Error("AI server did not return a system flag.")
    }
    if ((userFlag?.length ?? 0) > 200 || (systemFlag?.length ?? 0) > 200) {
      throw new Error("AI server returned an invalid flag.")
    }

    const machineId = chat.machine_id ?? sessionId
    const machineReference = firestore.collection(MACHINE_COLLECTION).doc(machineId)
    const now = new Date().toISOString()

    transaction.set(
      machineReference,
      {
        id: machineId,
        ai_session_id: chat.ai_session_id,
        created_by: `users/${ownerUserId}`,
        name: chat.answers.name,
        summary: `${chat.answers.theme}を学ぶためのマシンです。`,
        description: BUILDING_MACHINE_DESCRIPTION,
        file_path: "",
        level: difficultyToLevel(chat.answers.difficulty),
        published: chat.answers.visibility === "公開",
        status: "building",
        build_progress: 0,
        error_message: null,
        system_flag: systemFlag ?? "",
        user_flag: userFlag ?? "",
        tags: [chat.answers.theme],
        created_at: now,
      },
      { merge: true },
    )
    transaction.update(reference, {
      creation_status: "building",
      current_step: CHAT_STEPS.complete,
      machine_id: machineId,
      error_message: null,
      updated_at: Timestamp.now(),
    })
    return machineId
  })
}
