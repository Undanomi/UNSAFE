import "server-only"

import type { PoolClient } from "pg"
import { cancelAiSessionService, getAiSessionService } from "@/lib/ai/service"
import { resolveMachineFlag } from "@/lib/chat/flags"
import { queryDatabase, withDatabaseTransaction } from "@/lib/database/client"
import { BUILDING_MACHINE_DESCRIPTION } from "@/lib/machines/description"
import { toMachineLevel } from "@/lib/machines/difficulty"
import {
  CHAT_STEPS,
  type ChatAnswers,
  type ChatCreationFailure,
  type ChatCreationStatus,
  type ChatSession,
  type ChatSessionSummary,
  EMPTY_CHAT_ANSWERS,
} from "@/stores/chat"

type ChatSessionRow = {
  ai_session_id: string
  owner_user_id: string
  name: string
  current_step: number
  basic_ready: boolean
  answers: ChatAnswers
  creation_status: ChatCreationStatus
  creation_failure?: ChatCreationFailure | null
  machine_id: string | null
  error_message: string | null
  created_at: Date
  updated_at: Date
}

function toChatSession(row: ChatSessionRow): ChatSession {
  return {
    id: row.ai_session_id,
    name: row.name,
    status: row.basic_ready ? "基本設定完了" : "入力中",
    initialStep: row.current_step ?? CHAT_STEPS.machineName,
    initialAnswers: { ...EMPTY_CHAT_ANSWERS, ...row.answers },
    creationStatus: row.creation_status ?? "input",
    creationFailure: row.creation_failure ?? null,
    machineId: row.machine_id ?? null,
  }
}

export async function createChatSessionService(
  ownerUserId: string,
  aiSessionId: string,
  answers: ChatAnswers,
  currentStep: number,
  basicReady: boolean,
): Promise<ChatSession> {
  const result = await queryDatabase<ChatSessionRow>(
    `INSERT INTO chat_sessions
      (ai_session_id, owner_user_id, name, current_step, basic_ready, answers)
     VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING *`,
    [aiSessionId, ownerUserId, answers.name.trim(), currentStep, basicReady, answers],
  )
  return toChatSession(result.rows[0])
}

export async function getChatSessionService(
  ownerUserId: string,
  sessionId: string,
): Promise<ChatSession | null> {
  const result = await queryDatabase<ChatSessionRow>(
    "SELECT * FROM chat_sessions WHERE ai_session_id = $1 AND owner_user_id = $2",
    [sessionId, ownerUserId],
  )
  return result.rows[0] ? toChatSession(result.rows[0]) : null
}

export async function getChatSessionPageService(
  ownerUserId: string,
  sessionId: string,
): Promise<ChatSession | null> {
  const session = await getChatSessionService(ownerUserId, sessionId)
  if (!session) return null

  const isCreationRunning =
    session.creationStatus === "generating_scenario" || session.creationStatus === "building"
  const needsFailureDetails =
    session.creationStatus === "failed" && session.creationFailure === null
  if (!isCreationRunning && !needsFailureDetails) return session

  const aiSession = await getAiSessionService(ownerUserId, sessionId)
  const runtimeMatches =
    (session.creationStatus === "generating_scenario" &&
      aiSession.status === "generating_scenario") ||
    (session.creationStatus === "building" &&
      ["generating_code", "build_queued", "building"].includes(aiSession.status))
  if (runtimeMatches) return session

  if (aiSession.status === "completed") {
    await setChatCreationStatusService(ownerUserId, sessionId, "completed")
    return { ...session, creationStatus: "completed", creationFailure: null }
  }
  if (aiSession.status === "failed") {
    const failure: ChatCreationFailure = aiSession.failure
      ? {
          kind: aiSession.failure.kind,
          summary: aiSession.failure.summary,
          suggestions: [],
        }
      : {
          kind: "system",
          summary: "マシンを作成できませんでした。",
          suggestions: [],
        }
    await setChatCreationFailureService(ownerUserId, sessionId, failure)
    return { ...session, creationStatus: "failed", creationFailure: failure }
  }
  if (aiSession.status !== "cancelled") {
    await cancelAiSessionService(ownerUserId, sessionId)
  }

  await setChatCreationCancelledService(ownerUserId, sessionId)
  return { ...session, creationStatus: "cancelled", creationFailure: null }
}

export async function listChatSessionsService(ownerUserId: string): Promise<ChatSessionSummary[]> {
  const result = await queryDatabase<ChatSessionRow>(
    `SELECT * FROM chat_sessions
     WHERE owner_user_id = $1
     ORDER BY updated_at DESC, ai_session_id ASC`,
    [ownerUserId],
  )
  return result.rows.map((row) => {
    const session = toChatSession(row)
    return { id: session.id, name: session.name, status: session.status }
  })
}

export async function canModifyMachineCreationService(
  ownerUserId: string,
  sessionId: string,
): Promise<boolean> {
  const result = await queryDatabase<{ allowed: boolean }>(
    `SELECT EXISTS (
       SELECT 1 FROM chat_sessions c
       WHERE c.ai_session_id = $1 AND c.owner_user_id = $2
         AND c.creation_status <> 'completed'
         AND NOT EXISTS (
           SELECT 1 FROM machines m WHERE m.id = c.machine_id AND m.status = 'ready'
         )
     ) AS allowed`,
    [sessionId, ownerUserId],
  )
  return result.rows[0]?.allowed ?? false
}

export async function saveChatProgressService(
  ownerUserId: string,
  sessionId: string,
  answers: ChatAnswers,
  currentStep: number,
  basicReady: boolean,
): Promise<ChatSession | null> {
  const result = await queryDatabase<ChatSessionRow>(
    `UPDATE chat_sessions SET
       name = $3, current_step = $4, basic_ready = $5, answers = $6, updated_at = now()
     WHERE ai_session_id = $1 AND owner_user_id = $2
       AND creation_status <> 'completed'
       AND NOT EXISTS (
         SELECT 1 FROM machines m WHERE m.id = chat_sessions.machine_id AND m.status = 'ready'
       )
     RETURNING *`,
    [sessionId, ownerUserId, answers.name.trim(), currentStep, basicReady, answers],
  )
  return result.rows[0] ? toChatSession(result.rows[0]) : null
}

export async function setChatCreationStatusService(
  ownerUserId: string,
  sessionId: string,
  creationStatus: ChatCreationStatus,
): Promise<boolean> {
  const result = await queryDatabase(
    `UPDATE chat_sessions SET
       creation_status = $3, creation_failure = NULL, error_message = NULL,
       updated_at = now()
     WHERE ai_session_id = $1 AND owner_user_id = $2
       AND (
         $3 = 'completed'
         OR (
           creation_status <> 'completed'
           AND NOT EXISTS (
             SELECT 1 FROM machines m WHERE m.id = chat_sessions.machine_id AND m.status = 'ready'
           )
         )
       )`,
    [sessionId, ownerUserId, creationStatus],
  )
  return result.rowCount === 1
}

export async function setChatCreationFailureService(
  ownerUserId: string,
  sessionId: string,
  failure: ChatCreationFailure,
): Promise<boolean> {
  const result = await queryDatabase(
    `UPDATE chat_sessions SET
       creation_status = 'failed', creation_failure = $3::jsonb,
       error_message = $4, updated_at = now()
     WHERE ai_session_id = $1 AND owner_user_id = $2
       AND creation_status <> 'completed'
       AND NOT EXISTS (
         SELECT 1 FROM machines m WHERE m.id = chat_sessions.machine_id AND m.status = 'ready'
       )`,
    [sessionId, ownerUserId, failure, failure.summary],
  )
  return result.rowCount === 1
}

export async function setChatCreationCancelledService(
  ownerUserId: string,
  sessionId: string,
): Promise<boolean> {
  return withDatabaseTransaction(async (client) => {
    const chat = await lockOwnedChat(client, ownerUserId, sessionId)
    if (!chat || (await isCompletedMachine(client, chat))) return false

    await client.query(
      `UPDATE chat_sessions SET
         creation_status = 'cancelled', creation_failure = NULL,
         error_message = NULL, updated_at = now()
       WHERE ai_session_id = $1 AND owner_user_id = $2`,
      [sessionId, ownerUserId],
    )
    if (chat.machine_id) {
      await client.query(
        `UPDATE machines SET status = 'cancelled', error_message = NULL, updated_at = now()
         WHERE id = $1 AND created_by = $2`,
        [chat.machine_id, ownerUserId],
      )
    }
    return true
  })
}

export async function setChatCreationReadyService(
  ownerUserId: string,
  sessionId: string,
): Promise<boolean> {
  return withDatabaseTransaction(async (client) => {
    const chat = await lockOwnedChat(client, ownerUserId, sessionId)
    if (!chat || (await isCompletedMachine(client, chat))) return false

    await client.query(
      `UPDATE chat_sessions SET
         creation_status = 'input', creation_failure = NULL,
         error_message = NULL, updated_at = now()
       WHERE ai_session_id = $1 AND owner_user_id = $2`,
      [sessionId, ownerUserId],
    )
    if (chat.machine_id) {
      await client.query(
        `UPDATE machines SET status = 'cancelled', error_message = NULL, updated_at = now()
         WHERE id = $1 AND created_by = $2`,
        [chat.machine_id, ownerUserId],
      )
    }
    return true
  })
}

async function lockOwnedChat(client: PoolClient, ownerUserId: string, sessionId: string) {
  const result = await client.query<ChatSessionRow>(
    `SELECT * FROM chat_sessions
     WHERE ai_session_id = $1 AND owner_user_id = $2
     FOR UPDATE`,
    [sessionId, ownerUserId],
  )
  return result.rows[0] ?? null
}

async function isCompletedMachine(client: PoolClient, chat: ChatSessionRow): Promise<boolean> {
  if (chat.creation_status === "completed") return true
  if (!chat.machine_id) return false
  const result = await client.query<{ completed: boolean }>(
    "SELECT EXISTS (SELECT 1 FROM machines WHERE id = $1 AND status = 'ready') AS completed",
    [chat.machine_id],
  )
  return result.rows[0]?.completed ?? false
}

export async function createMachineDocumentService(
  ownerUserId: string,
  sessionId: string,
  generated: { userFlag: string | null; systemFlag: string | null; tags: string[] },
): Promise<string | null> {
  return withDatabaseTransaction(async (client) => {
    const chat = await lockOwnedChat(client, ownerUserId, sessionId)
    if (!chat || (await isCompletedMachine(client, chat))) return null
    if (!chat.answers.difficulty) throw new Error("Machine difficulty is missing.")

    const userFlag = resolveMachineFlag(chat.answers.needsUserFlag, generated.userFlag)
    const systemFlag = resolveMachineFlag(chat.answers.needsSystemFlag, generated.systemFlag)
    if (chat.answers.needsUserFlag && !userFlag) {
      throw new Error("AI server did not return a user flag.")
    }
    if (chat.answers.needsSystemFlag && !systemFlag) {
      throw new Error("AI server did not return a system flag.")
    }
    if (userFlag.length > 200 || systemFlag.length > 200) {
      throw new Error("AI server returned an invalid flag.")
    }
    const tags = [
      ...new Set(
        generated.tags
          .filter((tag): tag is string => typeof tag === "string")
          .map((tag) => tag.trim())
          .filter((tag) => tag.length > 0 && tag.length <= 30),
      ),
    ].slice(0, 5)
    if (tags.length === 0) throw new Error("AI server did not return scenario tags.")

    const machineId = chat.machine_id ?? sessionId
    const machineResult = await client.query(
      `INSERT INTO machines
        (id, ai_session_id, created_by, name, description, file_path, level,
         published, status, build_progress, system_flag, user_flag, tags)
       VALUES ($1, $2, $3, $4, $5, '', $6, $7, 'building', 0, $8, $9, $10)
       ON CONFLICT (id) DO UPDATE SET
         ai_session_id = EXCLUDED.ai_session_id,
         name = EXCLUDED.name,
         level = EXCLUDED.level,
         published = EXCLUDED.published,
         status = 'building',
         build_progress = 0,
         description = EXCLUDED.description,
         error_message = NULL,
         system_flag = EXCLUDED.system_flag,
         user_flag = EXCLUDED.user_flag,
         tags = EXCLUDED.tags,
         updated_at = now()
       WHERE machines.created_by = EXCLUDED.created_by AND machines.status <> 'ready'`,
      [
        machineId,
        chat.ai_session_id,
        ownerUserId,
        chat.answers.name,
        BUILDING_MACHINE_DESCRIPTION,
        toMachineLevel(chat.answers.difficulty),
        chat.answers.visibility === "公開",
        systemFlag,
        userFlag,
        tags,
      ],
    )
    if (machineResult.rowCount !== 1) {
      throw new Error("Machine belongs to a different user.")
    }
    const chatResult = await client.query(
      `UPDATE chat_sessions SET
         creation_status = 'building', current_step = $3, machine_id = $4,
         creation_failure = NULL, error_message = NULL, updated_at = now()
       WHERE ai_session_id = $1 AND owner_user_id = $2`,
      [sessionId, ownerUserId, CHAT_STEPS.complete, machineId],
    )
    if (chatResult.rowCount !== 1) throw new Error("Chat session could not be updated.")
    return machineId
  })
}
