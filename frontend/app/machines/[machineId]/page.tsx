import {
  MachineDetailView,
  MissingMachine,
} from "@/app/machines/[machineId]/_components/machine-detail"
import { AppShell } from "@/components/app-shell"
import { machineDetails } from "@/stores/machine-detail"

type MachineDetailPageProps = {
  params: Promise<{ machineId: string }>
}

export default async function MachineDetailPage({ params }: MachineDetailPageProps) {
  const { machineId } = await params
  const machine = machineDetails[machineId]

  return (
    <AppShell>{machine ? <MachineDetailView machine={machine} /> : <MissingMachine />}</AppShell>
  )
}
