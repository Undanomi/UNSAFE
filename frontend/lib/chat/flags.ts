export function resolveMachineFlag(requested: boolean | null, aiFlag: string | null): string {
  return requested === false ? "" : (aiFlag?.trim() ?? "")
}
