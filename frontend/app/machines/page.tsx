import { MachineList } from "@/app/machines/_components/machine-list"
import { AppShell } from "@/components/app-shell"
import { MACHINE_LIST } from "@/stores/machine-list"

export default function MachinesPage() {
  return (
    <AppShell>
      <MachineList machines={MACHINE_LIST} />
    </AppShell>
  )
}
