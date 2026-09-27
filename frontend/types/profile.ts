import type { MachineRecord } from "@/types/postgres"

export type ProfileMachine = {
  id: string
  name: string
  level: MachineRecord["level"]
  authorId: string
  authorName: string
  createdAt: string
  solvedAt?: string
}

export type UserProfile = {
  id: string
  name: string
  initial: string
  bio: string
  avatarUrl?: string
  createdMachines: ProfileMachine[]
  solvedMachines: ProfileMachine[]
}
