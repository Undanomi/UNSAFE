import "server-only"

import type { ChatAnswers } from "@/stores/chat"
import type { MachineGuidance } from "@/stores/machine-detail"

const REQUEST_TIMEOUT_MS = 30_000

export type AiSessionResponse = {
  session_id: string
  status:
    | "created"
    | "ready"
    | "generating_scenario"
    | "scenario_ready"
    | "generating_code"
    | "build_queued"
    | "building"
    | "completed"
    | "failed"
    | "cancelled"
  build_status: string | null
  build_progress: number
  download_url: string | null
  user_flag: string | null
  system_flag: string | null
  scenario: {
    scenario_id: string
    title: string
    scenario_description: string
    definition: string
  } | null
}

type DownloadURLResponse = {
  download_url: string
}

function getAiServerUrl(): string {
  const configuredUrl = process.env.AI_SERVER_URL?.trim()
  if (!configuredUrl) {
    throw new Error("AI_SERVER_URL is not configured.")
  }
  try {
    return new URL(configuredUrl).toString().replace(/\/$/, "")
  } catch {
    throw new Error("AI_SERVER_URL is not a valid URL.")
  }
}

async function parseAiResponse(response: Response): Promise<AiSessionResponse> {
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`AI server returned ${response.status}: ${body.slice(0, 500)}`)
  }
  return (await response.json()) as AiSessionResponse
}

function userHeaders(ownerUserId: string): HeadersInit {
  return { "X-Authenticated-User-ID": ownerUserId }
}

export async function createAiSessionService(ownerUserId: string): Promise<string> {
  const response = await fetch(`${getAiServerUrl()}/v1/sessions`, {
    method: "POST",
    headers: userHeaders(ownerUserId),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  return (await parseAiResponse(response)).session_id
}

export async function saveMachineInformationService(
  ownerUserId: string,
  sessionId: string,
  answers: ChatAnswers,
): Promise<void> {
  const response = await fetch(
    `${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}/machine-information`,
    {
      method: "PUT",
      headers: { ...userHeaders(ownerUserId), "Content-Type": "application/json" },
      body: JSON.stringify({
        name: answers.name.trim(),
        visibility: answers.visibility,
        theme: answers.theme.trim(),
        difficulty: answers.difficulty,
        needs_user_flag: answers.needsUserFlag,
        user_flag_details: answers.userFlagDetails.trim(),
        needs_system_flag: answers.needsSystemFlag,
        system_flag_details: answers.systemFlagDetails.trim(),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  )
  await parseAiResponse(response)
}

export async function openScenarioStreamService(
  ownerUserId: string,
  sessionId: string,
): Promise<Response> {
  return fetch(
    `${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}/scenarios/events`,
    {
      method: "GET",
      headers: userHeaders(ownerUserId),
      cache: "no-store",
    },
  )
}

export async function startMachineBuildService(
  ownerUserId: string,
  sessionId: string,
  scenarioId?: string,
): Promise<AiSessionResponse> {
  const response = await fetch(
    `${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}/machines`,
    {
      method: "POST",
      headers: { ...userHeaders(ownerUserId), "Content-Type": "application/json" },
      body: JSON.stringify(scenarioId ? { scenario_id: scenarioId } : {}),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  )
  return parseAiResponse(response)
}

export async function getAiSessionService(
  ownerUserId: string,
  sessionId: string,
): Promise<AiSessionResponse> {
  const response = await fetch(`${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: "GET",
    headers: userHeaders(ownerUserId),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  return parseAiResponse(response)
}

export async function generateAiGuidanceService(
  ownerUserId: string,
  sessionId: string,
  acquiredFlags: Array<"user" | "system">,
): Promise<MachineGuidance> {
  const response = await fetch(
    `${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}/guidance`,
    {
      method: "POST",
      headers: { ...userHeaders(ownerUserId), "Content-Type": "application/json" },
      body: JSON.stringify({ acquired_flags: acquiredFlags }),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  )
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`AI server returned ${response.status}: ${body.slice(0, 500)}`)
  }
  return (await response.json()) as MachineGuidance
}

export async function cancelAiSessionService(
  ownerUserId: string,
  sessionId: string,
): Promise<AiSessionResponse> {
  const response = await fetch(
    `${getAiServerUrl()}/v1/sessions/${encodeURIComponent(sessionId)}/cancel`,
    {
      method: "POST",
      headers: userHeaders(ownerUserId),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  )
  return parseAiResponse(response)
}

export async function openAiMachineDownloadService(
  ownerUserId: string,
  sessionId: string,
  rangeHeader: string | null,
  ifRangeHeader: string | null,
): Promise<Response> {
  const aiServerUrl = getAiServerUrl()
  const urlResponse = await fetch(
    `${aiServerUrl}/v1/sessions/${encodeURIComponent(sessionId)}/download-url`,
    {
      method: "POST",
      headers: userHeaders(ownerUserId),
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    },
  )
  if (!urlResponse.ok) {
    const body = await urlResponse.text()
    throw new Error(`AI server returned ${urlResponse.status}: ${body.slice(0, 500)}`)
  }

  const payload = (await urlResponse.json()) as DownloadURLResponse
  const downloadUrl = new URL(payload.download_url)
  if (downloadUrl.origin !== new URL(aiServerUrl).origin) {
    throw new Error("AI server returned an unexpected download URL.")
  }

  const headers = new Headers()
  if (rangeHeader) headers.set("Range", rangeHeader)
  if (ifRangeHeader) headers.set("If-Range", ifRangeHeader)
  return fetch(downloadUrl, {
    headers,
    cache: "no-store",
    redirect: "error",
  })
}
