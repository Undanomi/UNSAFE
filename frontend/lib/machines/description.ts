export const BUILDING_MACHINE_DESCRIPTION =
  "AIがシナリオとマシンを生成しています。完了までしばらくお待ちください。"

export function completedMachineDescription(
  machineName: string,
  scenarioDescription: string | null | undefined,
): string {
  const description = scenarioDescription?.trim()
  if (description) return description
  return `${machineName}のセキュリティ学習シナリオです。マシンを調査し、設定されたフラグを獲得してください。`
}
