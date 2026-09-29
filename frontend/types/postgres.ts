export type UserRecord = {
  id: string
  name: string
  bio: string
  icon_url: string
  theme: "light" | "dark"
  created_at: Date
  updated_at: Date
  profile_completed: boolean
}

export type MachineRecord = {
  id: string
  created_by: string
  name: string
  description: string
  file_path: string
  level: "very_easy" | "easy" | "medium" | "hard"
  published: boolean
  status: "created" | "building" | "ready" | "failed" | "cancelled" | "preparing" | "deleted"
  system_flag: string
  user_flag: string
  tags: string[]
  created_at: Date
  updated_at: Date
  ai_session_id: string | null
  build_progress: number
  error_message: string | null
}
