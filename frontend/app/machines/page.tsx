import { MachineList } from "@/app/machines/_components/machine-list"
import { AppShell } from "@/components/app-shell"
import { machineList } from "@/stores/machine-list"

export default function MachinesPage() {
  return (
    <AppShell>
      <MachineList machines={machineList} />
    </AppShell>
  )
}
