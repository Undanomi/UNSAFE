export type ProfileMachine = {
  id: string
  name: string
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
