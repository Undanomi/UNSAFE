import "server-only"

import { createHash, timingSafeEqual } from "node:crypto"
import { FieldValue } from "firebase-admin/firestore"
import {
  type AiSessionResponse,
  getAiSessionService,
  openAiMachineDownloadService,
  startMachineBuildService,
} from "@/lib/ai/service"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import {
  BUILDING_MACHINE_DESCRIPTION,
  completedMachineDescription,
} from "@/lib/machines/description"
import type { MachineBuildState, MachineDetail } from "@/stores/machine-detail"
import type { MachinesDocument } from "@/types/firestore"

function formatCreatedAt(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" }).format(date)
}

function toDifficulty(level: MachinesDocument["level"]): MachineDetail["difficulty"] {
  if (level === "hard") return "High"
  if (level === "medium") return "Medium"
  return "Easy"
}

function toMachineBuildState(session: AiSessionResponse): MachineBuildState {
  if (session.status === "completed") {
    return { status: "ready", progress: 100 }
  }
  if (session.status === "failed") {
    return {
      status: "failed",
      progress: Math.max(0, Math.min(100, session.build_progress)),
    }
  }
  if (session.status === "cancelled") {
    return {
      status: "cancelled",
      progress: Math.max(0, Math.min(100, session.build_progress)),
    }
  }
  return {
    status: session.status === "generating_code" ? "preparing" : "building",
    progress: Math.max(0, Math.min(100, session.build_progress)),
  }
}

function machineOwnerId(machine: MachinesDocument) {
  return machine.created_by.replace(/^users\//, "")
}

async function saveMachineBuildState(
  machineId: string,
  aiSessionId: string,
  state: MachineBuildState,
) {
  const firestore = getFirebaseAdminFirestore()
  const chatStatus =
    state.status === "ready"
      ? "completed"
      : state.status === "failed"
        ? "failed"
        : state.status === "cancelled"
          ? "cancelled"
          : "building"

  const batch = firestore.batch()
  batch.update(firestore.collection("machines").doc(machineId), {
    status: state.status,
    build_progress: state.progress,
    error_message: null,
    ...(state.description ? { description: state.description } : {}),
  })
  batch.update(firestore.collection("chat_sessions").doc(aiSessionId), {
    creation_status: chatStatus,
    error_message: null,
  })
  await batch.commit()
}

async function getMachineDocument(machineId: string) {
  const snapshot = await getFirebaseAdminFirestore().collection("machines").doc(machineId).get()
  return snapshot.exists ? (snapshot.data() as MachinesDocument) : null
}

export async function getMachineDetailService(
  viewerUserId: string,
  machineId: string,
): Promise<MachineDetail | null> {
  const firestore = getFirebaseAdminFirestore()
  const snapshot = await firestore.collection("machines").doc(machineId).get()
  if (!snapshot.exists) return null

  const machine = snapshot.data() as MachinesDocument
  const ownerUserId = machineOwnerId(machine)
  const isOwner = ownerUserId === viewerUserId
  if (!machine.published && !isOwner) return null

  const ownerSnapshot = await firestore.collection("users").doc(ownerUserId).get()
  const owner = ownerSnapshot.data() as { name?: string } | undefined
  let description = machine.description
  if (
    machine.status === "ready" &&
    description === BUILDING_MACHINE_DESCRIPTION &&
    machine.ai_session_id
  ) {
    try {
      const aiSession = await getAiSessionService(ownerUserId, machine.ai_session_id)
      if (aiSession.status === "completed") {
        description = completedMachineDescription(
          machine.name,
          aiSession.scenario?.scenario_description,
        )
        await snapshot.ref.update({ description })
      }
    } catch (error) {
      console.error("Failed to refresh the completed machine description.", error)
    }
  }

  return {
    id: snapshot.id,
    name: machine.name,
    author: owner?.name || "ユーザー",
    createdAt: formatCreatedAt(machine.created_at),
    visibility: machine.published ? "公開" : "非公開",
    theme: machine.tags[0] ?? "セキュリティ",
    difficulty: toDifficulty(machine.level),
    summary: machine.summary,
    description,
    buildProgress: machine.build_progress ?? 0,
    canRetry: isOwner,
    status: machine.status,
    userFlag: machine.user_flag
      ? { kind: "user", label: "ユーザーフラグ", machineId: snapshot.id }
      : null,
    systemFlag: machine.system_flag
      ? { kind: "system", label: "システムフラグ", machineId: snapshot.id }
      : null,
  }
}

export async function getMachineBuildStateService(
  viewerUserId: string,
  machineId: string,
): Promise<MachineBuildState | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine?.ai_session_id) return null

  const ownerUserId = machineOwnerId(machine)
  const isOwner = ownerUserId === viewerUserId
  if (!machine.published && !isOwner) return null

  const aiSession = await getAiSessionService(ownerUserId, machine.ai_session_id)
  const buildState = toMachineBuildState(aiSession)
  const description =
    buildState.status === "ready"
      ? completedMachineDescription(machine.name, aiSession.scenario?.scenario_description)
      : undefined
  const state = { ...buildState, ...(description ? { description } : {}) }
  await saveMachineBuildState(machineId, machine.ai_session_id, state)
  return state
}

export async function retryMachineBuildService(
  ownerUserId: string,
  machineId: string,
): Promise<MachineBuildState | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine?.ai_session_id || machineOwnerId(machine) !== ownerUserId) return null

  const current = await getAiSessionService(ownerUserId, machine.ai_session_id)
  if (current.status !== "failed" && current.status !== "cancelled") {
    const buildState = toMachineBuildState(current)
    const description =
      buildState.status === "ready"
        ? completedMachineDescription(machine.name, current.scenario?.scenario_description)
        : undefined
    const state = { ...buildState, ...(description ? { description } : {}) }
    await saveMachineBuildState(machineId, machine.ai_session_id, state)
    return state
  }

  const restarted = await startMachineBuildService(ownerUserId, machine.ai_session_id)
  const buildState = toMachineBuildState(restarted)
  const description =
    buildState.status === "ready"
      ? completedMachineDescription(machine.name, restarted.scenario?.scenario_description)
      : undefined
  const state = { ...buildState, ...(description ? { description } : {}) }
  await saveMachineBuildState(machineId, machine.ai_session_id, state)
  return state
}

export async function openMachineDownloadService(
  viewerUserId: string,
  machineId: string,
  rangeHeader: string | null,
  ifRangeHeader: string | null,
): Promise<Response | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine?.ai_session_id) return null

  const ownerUserId = machineOwnerId(machine)
  if (!machine.published && ownerUserId !== viewerUserId) return null
  return openAiMachineDownloadService(
    ownerUserId,
    machine.ai_session_id,
    rangeHeader,
    ifRangeHeader,
  )
}

export async function verifyMachineFlagService(
  viewerUserId: string,
  machineId: string,
  kind: "user" | "system",
  answer: string,
): Promise<boolean | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine) return null

  const ownerUserId = machineOwnerId(machine)
  if (!machine.published && ownerUserId !== viewerUserId) return null
  const expected = kind === "user" ? machine.user_flag : machine.system_flag
  if (!expected) return null

  const expectedDigest = createHash("sha256").update(expected, "utf8").digest()
  const answerDigest = createHash("sha256").update(answer.trim(), "utf8").digest()
  const correct = timingSafeEqual(expectedDigest, answerDigest)
  if (correct) {
    await getFirebaseAdminFirestore()
      .collection("users")
      .doc(viewerUserId)
      .update({
        solved_machines: FieldValue.arrayUnion(`machines/${machineId}`),
      })
  }
  return correct
}
