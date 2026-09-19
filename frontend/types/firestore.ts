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
}
