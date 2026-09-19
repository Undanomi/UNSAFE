/** users コレクションのドキュメント定義 */
export type UsersDocument = {
  id: string
  name: string
  bio: string
  icon_url: string
  theme: "light" | "dark"
  own_machines: string[] // machines コレクションのドキュメントパス
  solved_machines: string[] // machines コレクションのドキュメントパス
  created_at: string
  profile_completed: boolean
}

/** machines コレクションのドキュメント定義 */
export type MachinesDocument = {
  id: string
  created_by: string // users コレクションのドキュメントパス
  name: string
  summary: string
  description: string
  file_path: string
  level: "easy" | "medium" | "hard"
  published: boolean
  status: "created" | "building" | "ready" | "failed" | "preparing" | "deleted"
  system_flag: string
  user_flag: string
  tags: string[]
  created_at: string
  ai_session_id?: string
  build_progress?: number
}

/** chat_sessions コレクションのドキュメント定義 */
export type ChatSessionsDocument = {
  ai_session_id: string
  owner_user_id: string
  name: string
  current_step: number
  basic_ready: boolean
  answers: {
    name: string
    visibility: "非公開" | "公開" | ""
    theme: string
    difficulty: "Very Easy" | "Easy" | "Medium" | "High" | ""
    needsUserFlag: boolean | null
    userFlagDetails: string
    needsSystemFlag: boolean | null
    systemFlagDetails: string
  }
  creation_status: "input" | "generating_scenario" | "building" | "completed" | "failed"
  machine_id: string | null
  created_at: FirebaseFirestore.Timestamp
  updated_at: FirebaseFirestore.Timestamp
}
