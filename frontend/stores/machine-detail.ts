import { MACHINE_LIST, type MachineSummary } from "@/stores/machine-list"

export type FlagDefinition = {
  label: string
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
  userFlag: FlagDefinition
  systemFlag: FlagDefinition
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
        label: "ユーザーフラグ",
      },
      systemFlag: {
        label: "システムフラグ",
      },
    } satisfies MachineDetail,
  ]),
)

export const MACHINE_DETAILS: Record<string, MachineDetail> = {
  ...DEFAULT_MACHINE_DETAILS,
}
