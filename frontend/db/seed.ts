import process from "node:process"
import { Pool } from "pg"

const LOCAL_DATABASE_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"])

function developmentDatabaseUrl(): string {
  if (process.env.NODE_ENV === "production") {
    throw new Error("Seed data cannot be applied in production.")
  }

  const value = process.env.DEV_DATABASE_URL
  if (!value) throw new Error("DEV_DATABASE_URL is not configured.")

  const url = new URL(value)
  if (!LOCAL_DATABASE_HOSTS.has(url.hostname)) {
    throw new Error("Seed data can only be applied to a local DEV_DATABASE_URL.")
  }
  return value
}

const users = [
  {
    id: "seed-user-alice",
    name: "アリス",
    bio: "Webセキュリティを学習中です。",
    iconUrl: "",
    theme: "dark",
    profileCompleted: true,
  },
  {
    id: "seed-user-bob",
    name: "ボブ",
    bio: "コンテナとネットワークが好きです。",
    iconUrl: "",
    theme: "light",
    profileCompleted: true,
  },
] as const

const machines = [
  {
    id: "seed-machine-public-ready",
    aiSessionId: "seed-chat-completed",
    createdBy: "seed-user-alice",
    name: "公開Web認証ラボ",
    summary: "認証回避の基本を学ぶ公開マシンです。",
    description: "ログイン処理に潜む問題を調査し、フラグを取得してください。",
    level: "easy",
    published: true,
    status: "ready",
    progress: 100,
    systemFlag: "FLAG{seed-system-flag}",
    userFlag: "FLAG{seed-user-flag}",
    tags: ["Web セキュリティ", "認証・認可"],
  },
  {
    id: "seed-machine-private-building",
    aiSessionId: "seed-chat-building",
    createdBy: "seed-user-bob",
    name: "非公開コンテナ調査",
    summary: "ビルド中の非公開マシンです。",
    description: "マシンを準備しています。しばらくお待ちください。",
    level: "medium",
    published: true,
    status: "building",
    progress: 65,
    systemFlag: "",
    userFlag: "",
    tags: ["コンテナ", "ネットワーク"],
  },
] as const

const chats = [
  {
    id: "seed-chat-completed",
    ownerUserId: "seed-user-alice",
    name: "公開Web認証ラボ",
    currentStep: 9,
    basicReady: true,
    answers: {
      name: "公開Web認証ラボ",
      visibility: "公開",
      theme: "Web セキュリティ",
      difficulty: "Easy",
      needsUserFlag: true,
      userFlagDetails: "一般ユーザー権限で取得できるフラグ",
      needsSystemFlag: true,
      systemFlagDetails: "管理者権限で取得できるフラグ",
    },
    creationStatus: "completed",
    machineId: "seed-machine-public-ready",
  },
  {
    id: "seed-chat-building",
    ownerUserId: "seed-user-bob",
    name: "非公開コンテナ調査",
    currentStep: 9,
    basicReady: true,
    answers: {
      name: "非公開コンテナ調査",
      visibility: "非公開",
      theme: "コンテナ",
      difficulty: "Medium",
      needsUserFlag: false,
      userFlagDetails: "",
      needsSystemFlag: false,
      systemFlagDetails: "",
    },
    creationStatus: "building",
    machineId: "seed-machine-private-building",
  },
  {
    id: "seed-chat-draft",
    ownerUserId: "seed-user-alice",
    name: "下書きネットワーク演習",
    currentStep: 4,
    basicReady: false,
    answers: {
      name: "下書きネットワーク演習",
      visibility: "非公開",
      theme: "ネットワーク",
      difficulty: "",
      needsUserFlag: null,
      userFlagDetails: "",
      needsSystemFlag: null,
      systemFlagDetails: "",
    },
    creationStatus: "input",
    machineId: null,
  },
] as const

async function main() {
  const pool = new Pool({ connectionString: developmentDatabaseUrl(), max: 1 })
  const client = await pool.connect()

  try {
    await client.query("BEGIN")

    for (const user of users) {
      await client.query(
        `INSERT INTO users (id, name, bio, icon_url, theme, profile_completed)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (id) DO UPDATE SET
           name = EXCLUDED.name,
           bio = EXCLUDED.bio,
           icon_url = EXCLUDED.icon_url,
           theme = EXCLUDED.theme,
           profile_completed = EXCLUDED.profile_completed,
           updated_at = now()`,
        [user.id, user.name, user.bio, user.iconUrl, user.theme, user.profileCompleted],
      )
    }

    for (const machine of machines) {
      await client.query(
        `INSERT INTO machines
          (id, ai_session_id, created_by, name, summary, description, file_path, level,
           published, status, build_progress, system_flag, user_flag, tags)
         VALUES ($1, $2, $3, $4, $5, $6, '', $7, $8, $9, $10, $11, $12, $13)
         ON CONFLICT (id) DO UPDATE SET
           ai_session_id = EXCLUDED.ai_session_id,
           created_by = EXCLUDED.created_by,
           name = EXCLUDED.name,
           summary = EXCLUDED.summary,
           description = EXCLUDED.description,
           level = EXCLUDED.level,
           published = EXCLUDED.published,
           status = EXCLUDED.status,
           build_progress = EXCLUDED.build_progress,
           system_flag = EXCLUDED.system_flag,
           user_flag = EXCLUDED.user_flag,
           tags = EXCLUDED.tags,
           updated_at = now()`,
        [
          machine.id,
          machine.aiSessionId,
          machine.createdBy,
          machine.name,
          machine.summary,
          machine.description,
          machine.level,
          machine.published,
          machine.status,
          machine.progress,
          machine.systemFlag,
          machine.userFlag,
          machine.tags,
        ],
      )
    }

    for (const chat of chats) {
      await client.query(
        `INSERT INTO chat_sessions
          (ai_session_id, owner_user_id, name, current_step, basic_ready, answers,
           creation_status, machine_id)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (ai_session_id) DO UPDATE SET
           owner_user_id = EXCLUDED.owner_user_id,
           name = EXCLUDED.name,
           current_step = EXCLUDED.current_step,
           basic_ready = EXCLUDED.basic_ready,
           answers = EXCLUDED.answers,
           creation_status = EXCLUDED.creation_status,
           machine_id = EXCLUDED.machine_id,
           updated_at = now()`,
        [
          chat.id,
          chat.ownerUserId,
          chat.name,
          chat.currentStep,
          chat.basicReady,
          chat.answers,
          chat.creationStatus,
          chat.machineId,
        ],
      )
    }

    await client.query(
      `INSERT INTO machine_solutions (user_id, machine_id)
       VALUES ('seed-user-bob', 'seed-machine-public-ready')
       ON CONFLICT (user_id, machine_id) DO NOTHING`,
    )
    await client.query("COMMIT")
    console.log("Seed data applied.")
  } catch (error) {
    await client.query("ROLLBACK")
    throw error
  } finally {
    client.release()
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
