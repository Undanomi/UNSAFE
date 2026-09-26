import "server-only"

import { createHash, timingSafeEqual } from "node:crypto"
import {
  type AiSessionResponse,
  generateAiGuidanceService,
  getAiSessionService,
  openAiMachineDownloadService,
  startMachineBuildService,
} from "@/lib/ai/service"
import { queryDatabase, withDatabaseTransaction } from "@/lib/database/client"
import {
  BUILDING_MACHINE_DESCRIPTION,
  completedMachineDescription,
} from "@/lib/machines/description"
import type { MachineBuildState, MachineDetail, MachineGuidance } from "@/types/machine-detail"
import type { MachineRecord } from "@/types/postgres"

function formatCreatedAt(value: Date | string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeZone: "Asia/Tokyo",
  }).format(date)
}

function toDifficulty(level: MachineRecord["level"]): MachineDetail["difficulty"] {
  if (level === "hard") return "High"
  if (level === "medium") return "Medium"
  return "Easy"
}

function formatWorkbenchCommand(command: { argv?: string[]; cwd?: string } | undefined) {
  if (!command?.argv?.length) return null
  const cwd = command.cwd ? ` (${command.cwd})` : ""
  return `$ ${command.argv.join(" ")}${cwd}`
}

function toWorkbenchLog(session: AiSessionResponse): MachineBuildState["workbench"] {
  const progress = session.source_workbench
  const report = progress?.report
  if (!report) return undefined
  const lines: string[] = []
  for (const observation of report.observations ?? []) {
    const command = formatWorkbenchCommand(observation.command)
    if (command) lines.push(command)
    if (observation.summary) lines.push(`[patch] ${observation.summary}`)
    if (observation.reason) lines.push(`[${observation.kind ?? "info"}] ${observation.reason}`)
    if (observation.error) lines.push(`[error] ${observation.error}`)
    if (observation.stdout) lines.push(...observation.stdout.trimEnd().split("\n"))
    if (observation.stderr) {
      lines.push(
        ...observation.stderr
          .trimEnd()
          .split("\n")
          .map((line) => `[stderr] ${line}`),
      )
    }
    if (typeof observation.exit_code === "number") {
      lines.push(`[exit ${observation.exit_code}]`)
    }
  }
  const activeCommand = formatWorkbenchCommand(report.active_command)
  if (activeCommand) lines.push(`${activeCommand} [実行中]`)
  if (lines.length === 0) {
    const summary = report.summary ?? report.error_message
    if (summary) lines.push(`[sandbox] ${summary}`)
  }
  return {
    status: report.status ?? "unknown",
    updatedAt: progress?.updated_at ?? null,
    lines: lines.slice(-100).map((line) => line.slice(0, 2_000)),
  }
}

function toMachineBuildState(
  session: AiSessionResponse,
  includeWorkbench = false,
): MachineBuildState {
  const workbench = includeWorkbench ? toWorkbenchLog(session) : undefined
  const shared = {
    progress: Math.max(0, Math.min(100, session.build_progress)),
    ...(workbench ? { workbench } : {}),
  }
  if (session.status === "completed") {
    return { ...shared, status: "ready", progress: 100 }
  }
  if (session.status === "failed") {
    return {
      ...shared,
      status: "failed",
      failure: session.failure
        ? {
            kind: session.failure.kind,
            summary: session.failure.summary,
            retryAllowed: session.failure.retry_allowed,
          }
        : null,
    }
  }
  if (session.status === "cancelled") {
    return {
      ...shared,
      status: "cancelled",
    }
  }
  return {
    ...shared,
    status: session.status === "generating_code" ? "preparing" : "building",
  }
}

async function saveMachineBuildState(
  machineId: string,
  aiSessionId: string,
  state: MachineBuildState,
) {
  const chatStatus =
    state.status === "ready"
      ? "completed"
      : state.status === "failed"
        ? "failed"
        : state.status === "cancelled"
          ? "cancelled"
          : "building"

  await withDatabaseTransaction(async (client) => {
    const machineUpdate = await client.query(
      `UPDATE machines SET
         status = $2, build_progress = $3, error_message = $5,
         description = COALESCE($4, description), updated_at = now()
       WHERE id = $1`,
      [
        machineId,
        state.status,
        state.progress,
        state.description ?? null,
        state.failure?.summary ?? null,
      ],
    )
    const chatUpdate = await client.query(
      `UPDATE chat_sessions SET
         creation_status = $2, error_message = $3, updated_at = now()
       WHERE ai_session_id = $1`,
      [aiSessionId, chatStatus, state.failure?.summary ?? null],
    )
    if (machineUpdate.rowCount !== 1 || chatUpdate.rowCount !== 1) {
      throw new Error("Machine build state could not be persisted.")
    }
  })
}

async function getMachineDocument(machineId: string) {
  const result = await queryDatabase<MachineRecord>("SELECT * FROM machines WHERE id = $1", [
    machineId,
  ])
  return result.rows[0] ?? null
}

export async function getMachineDetailService(
  viewerUserId: string,
  machineId: string,
): Promise<MachineDetail | null> {
  const result = await queryDatabase<MachineRecord & { owner_name: string }>(
    `SELECT machines.*, users.name AS owner_name
     FROM machines
     JOIN users ON users.id = machines.created_by
     WHERE machines.id = $1`,
    [machineId],
  )
  const machine = result.rows[0]
  if (!machine) return null

  const ownerUserId = machine.created_by
  const isOwner = ownerUserId === viewerUserId
  if (!machine.published && !isOwner) return null

  const [guidanceResult, acquiredResult] = await Promise.all([
    queryDatabase<{ content: MachineGuidance }>(
      "SELECT content FROM machine_guidance WHERE user_id = $1 AND machine_id = $2",
      [viewerUserId, machineId],
    ),
    queryDatabase<{ flag_kind: "user" | "system" }>(
      "SELECT flag_kind FROM machine_flag_solutions WHERE user_id = $1 AND machine_id = $2",
      [viewerUserId, machineId],
    ),
  ])
  const acquiredFlags = new Set(acquiredResult.rows.map((row) => row.flag_kind))

  let description = machine.description
  let buildFailure: MachineBuildState["failure"] = null
  if (machine.status === "failed" && machine.ai_session_id) {
    try {
      const aiSession = await getAiSessionService(ownerUserId, machine.ai_session_id)
      buildFailure = toMachineBuildState(aiSession).failure ?? null
    } catch (error) {
      console.error("Failed to refresh the machine build failure.", error)
    }
  }
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
        await queryDatabase(
          "UPDATE machines SET description = $2, updated_at = now() WHERE id = $1",
          [machineId, description],
        )
      }
    } catch (error) {
      console.error("Failed to refresh the completed machine description.", error)
    }
  }

  return {
    id: machine.id,
    name: machine.name,
    author: machine.owner_name || "ユーザー",
    createdAt: formatCreatedAt(machine.created_at),
    visibility: machine.published ? "公開" : "非公開",
    theme: machine.tags[0] ?? "セキュリティ",
    difficulty: toDifficulty(machine.level),
    summary: machine.summary,
    description,
    buildProgress: machine.build_progress ?? 0,
    buildFailure,
    canRetry: isOwner && buildFailure?.retryAllowed !== false,
    status: machine.status,
    guidance: guidanceResult.rows[0]?.content ?? null,
    userFlag: machine.user_flag
      ? {
          acquired: acquiredFlags.has("user"),
          kind: "user",
          label: "ユーザーフラグ",
          machineId: machine.id,
        }
      : null,
    systemFlag: machine.system_flag
      ? {
          acquired: acquiredFlags.has("system"),
          kind: "system",
          label: "システムフラグ",
          machineId: machine.id,
        }
      : null,
  }
}

export async function generateMachineGuidanceService(
  viewerUserId: string,
  machineId: string,
  regenerate: boolean,
): Promise<MachineGuidance | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine?.ai_session_id || machine.status !== "ready") return null
  if (!machine.published && machine.created_by !== viewerUserId) return null

  if (!regenerate) {
    const existing = await queryDatabase<{ content: MachineGuidance }>(
      "SELECT content FROM machine_guidance WHERE user_id = $1 AND machine_id = $2",
      [viewerUserId, machineId],
    )
    if (existing.rows[0]) return existing.rows[0].content
  }

  const acquired = await queryDatabase<{ flag_kind: "user" | "system" }>(
    `SELECT flag_kind FROM machine_flag_solutions
     WHERE user_id = $1 AND machine_id = $2
     ORDER BY flag_kind`,
    [viewerUserId, machineId],
  )
  const guidance = await generateAiGuidanceService(
    machine.created_by,
    machine.ai_session_id,
    acquired.rows.map((row) => row.flag_kind),
  )

  if (regenerate) {
    await queryDatabase(
      `INSERT INTO machine_guidance (user_id, machine_id, content)
       VALUES ($1, $2, $3::jsonb)
       ON CONFLICT (user_id, machine_id) DO UPDATE SET
         content = EXCLUDED.content,
         generation = machine_guidance.generation + 1,
         updated_at = now()`,
      [viewerUserId, machineId, JSON.stringify(guidance)],
    )
    return guidance
  }

  const inserted = await queryDatabase<{ content: MachineGuidance }>(
    `INSERT INTO machine_guidance (user_id, machine_id, content)
     VALUES ($1, $2, $3::jsonb)
     ON CONFLICT (user_id, machine_id) DO NOTHING
     RETURNING content`,
    [viewerUserId, machineId, JSON.stringify(guidance)],
  )
  if (inserted.rows[0]) return inserted.rows[0].content
  const existing = await queryDatabase<{ content: MachineGuidance }>(
    "SELECT content FROM machine_guidance WHERE user_id = $1 AND machine_id = $2",
    [viewerUserId, machineId],
  )
  return existing.rows[0]?.content ?? null
}

export async function getMachineBuildStateService(
  viewerUserId: string,
  machineId: string,
): Promise<MachineBuildState | null> {
  const machine = await getMachineDocument(machineId)
  if (!machine?.ai_session_id) return null

  const ownerUserId = machine.created_by
  const isOwner = ownerUserId === viewerUserId
  if (!machine.published && !isOwner) return null

  const aiSession = await getAiSessionService(ownerUserId, machine.ai_session_id)
  const buildState = toMachineBuildState(aiSession, isOwner)
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
  if (!machine?.ai_session_id || machine.created_by !== ownerUserId) return null

  const current = await getAiSessionService(ownerUserId, machine.ai_session_id)
  if (current.failure?.retry_allowed === false) {
    return toMachineBuildState(current, true)
  }
  if (current.status !== "failed" && current.status !== "cancelled") {
    const buildState = toMachineBuildState(current, true)
    const description =
      buildState.status === "ready"
        ? completedMachineDescription(machine.name, current.scenario?.scenario_description)
        : undefined
    const state = { ...buildState, ...(description ? { description } : {}) }
    await saveMachineBuildState(machineId, machine.ai_session_id, state)
    return state
  }

  const restarted = await startMachineBuildService(ownerUserId, machine.ai_session_id)
  const buildState = toMachineBuildState(restarted, true)
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

  const ownerUserId = machine.created_by
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

  const ownerUserId = machine.created_by
  if (!machine.published && ownerUserId !== viewerUserId) return null
  const expected = kind === "user" ? machine.user_flag : machine.system_flag
  if (!expected) return null

  const expectedDigest = createHash("sha256").update(expected, "utf8").digest()
  const answerDigest = createHash("sha256").update(answer.trim(), "utf8").digest()
  const correct = timingSafeEqual(expectedDigest, answerDigest)
  if (correct) {
    await withDatabaseTransaction(async (client) => {
      await client.query(
        `INSERT INTO machine_flag_solutions (user_id, machine_id, flag_kind)
         VALUES ($1, $2, $3)
         ON CONFLICT (user_id, machine_id, flag_kind) DO NOTHING`,
        [viewerUserId, machineId, kind],
      )
      await client.query(
        `INSERT INTO machine_solutions (user_id, machine_id)
         VALUES ($1, $2)
         ON CONFLICT (user_id, machine_id) DO NOTHING`,
        [viewerUserId, machineId],
      )
    })
  }
  return correct
}
