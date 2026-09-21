import { MACHINE_LIST, type MachineSummary } from "@/stores/machine-list"
import type { MachineRecord } from "@/types/postgres"

export type FlagDefinition = {
  kind: "user" | "system"
  label: string
  machineId: string
}

export type MachineBuildState = {
  status: MachineRecord["status"]
  progress: number
  description?: string
}

export type MachineDetail = Pick<
  MachineSummary,
  | "id"
  | "name"
  | "author"
  | "createdAt"
  | "visibility"
  | "theme"
  | "difficulty"
  | "summary"
  | "description"
> & {
  buildProgress?: number
  canRetry?: boolean
  status?: MachineRecord["status"]
  userFlag: FlagDefinition | null
  systemFlag: FlagDefinition | null
}

const DEFAULT_MACHINE_DETAILS = Object.fromEntries(
  MACHINE_LIST.map((machine) => [
    machine.id,
    {
      id: machine.id,
      name: machine.name,
      author: machine.author,
      createdAt: machine.createdAt,
      visibility: machine.visibility,
      theme: machine.theme,
      difficulty: machine.difficulty,
      summary: machine.summary,
      description: machine.description,
      userFlag: {
        kind: "user",
        label: "ユーザーフラグ",
        machineId: machine.id,
      },
      systemFlag: {
        kind: "system",
        label: "システムフラグ",
        machineId: machine.id,
      },
    } satisfies MachineDetail,
  ]),
)

export const MACHINE_DETAILS: Record<string, MachineDetail> = {
  ...DEFAULT_MACHINE_DETAILS,
}
