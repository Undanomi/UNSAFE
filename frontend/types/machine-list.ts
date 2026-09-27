export type MachineVisibility = "公開" | "非公開"
export type MachineDifficulty = "Very Easy" | "Easy" | "Medium" | "High"

export type MachineSummary = {
  id: string
  name: string
  summary: string
  description: string
  author: string
  authorId: string
  createdAt: string
  visibility: MachineVisibility
  isOwned: boolean
  theme: string
  difficulty: MachineDifficulty
}
