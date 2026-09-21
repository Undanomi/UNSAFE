import "server-only"

import type { PoolClient } from "pg"
import { queryDatabase, withDatabaseTransaction } from "@/lib/database/client"
import { BUILDING_MACHINE_DESCRIPTION } from "@/lib/machines/description"
import {
  CHAT_STEPS,
  type ChatAnswers,
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
       creation_status = $3, error_message = NULL, updated_at = now()
     WHERE ai_session_id = $1 AND owner_user_id = $2`,
    [sessionId, ownerUserId, creationStatus],
  )
  return result.rowCount === 1
}

function difficultyToLevel(difficulty: ChatAnswers["difficulty"]) {
  if (difficulty === "Medium") return "medium"
  if (difficulty === "High") return "hard"
  return "easy"
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

export async function createMachineDocumentService(
  ownerUserId: string,
  sessionId: string,
  flags: { userFlag: string | null; systemFlag: string | null },
): Promise<string | null> {
  return withDatabaseTransaction(async (client) => {
    const chat = await lockOwnedChat(client, ownerUserId, sessionId)
    if (!chat) return null

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
    const machineResult = await client.query(
      `INSERT INTO machines
        (id, ai_session_id, created_by, name, summary, description, file_path, level,
         published, status, build_progress, system_flag, user_flag, tags)
       VALUES ($1, $2, $3, $4, $5, $6, '', $7, $8, 'building', 0, $9, $10, $11)
       ON CONFLICT (id) DO UPDATE SET
         ai_session_id = EXCLUDED.ai_session_id,
         name = EXCLUDED.name,
         summary = EXCLUDED.summary,
         level = EXCLUDED.level,
         published = EXCLUDED.published,
         system_flag = EXCLUDED.system_flag,
         user_flag = EXCLUDED.user_flag,
         tags = EXCLUDED.tags,
         updated_at = now()
       WHERE machines.created_by = EXCLUDED.created_by`,
      [
        machineId,
        chat.ai_session_id,
        ownerUserId,
        chat.answers.name,
        `${chat.answers.theme}を学ぶためのマシンです。`,
        BUILDING_MACHINE_DESCRIPTION,
        difficultyToLevel(chat.answers.difficulty),
        chat.answers.visibility === "公開",
        systemFlag ?? "",
        userFlag ?? "",
        [chat.answers.theme],
      ],
    )
    if (machineResult.rowCount !== 1) {
      throw new Error("Machine belongs to a different user.")
    }
    const chatResult = await client.query(
      `UPDATE chat_sessions SET
         creation_status = 'building', current_step = $3, machine_id = $4,
         error_message = NULL, updated_at = now()
       WHERE ai_session_id = $1 AND owner_user_id = $2`,
      [sessionId, ownerUserId, CHAT_STEPS.complete, machineId],
    )
    if (chatResult.rowCount !== 1) throw new Error("Chat session could not be updated.")
    return machineId
  })
}
