export type MachineVisibility = "公開" | "非公開"
export type MachineDifficulty = "Very Easy" | "Easy" | "Medium" | "High"

export type MachineSummary = {
  id: string
  name: string
  description: string
  author: string
  authorPublicId: string
  createdAt: string
  visibility: MachineVisibility
  isOwned: boolean
  difficulty: MachineDifficulty
}
