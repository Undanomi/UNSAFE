import type { MachineRecord } from "@/types/postgres"

export type ProfileMachine = {
  id: string
  name: string
  level: MachineRecord["level"]
  authorPublicId: string
  authorName: string
  createdAt: string
  solvedAt?: string
}

export type UserProfile = {
  publicId: string
  name: string
  initial: string
  bio: string
  avatarUrl?: string
  createdMachines: ProfileMachine[]
  solvedMachines: ProfileMachine[]
}
