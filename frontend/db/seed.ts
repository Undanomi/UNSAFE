import process from "node:process"
import { Pool } from "pg"

const DEVELOPMENT_DATABASE_NAME = "frontend_service"
const DEVELOPMENT_DATABASE_HOSTS = new Set([
  "frontend-postgres",
  "localhost",
  "127.0.0.1",
  "::1",
  "[::1]",
])

function developmentDatabaseUrl(): string {
  if (process.env.NODE_ENV === "production") {
    throw new Error("Seed data cannot be applied in production.")
  }

  const value = process.env.DATABASE_URL
  if (!value) throw new Error("DATABASE_URL is not configured.")

  const url = new URL(value)
  const databaseName = decodeURIComponent(url.pathname.replace(/^\//, ""))
  if (!DEVELOPMENT_DATABASE_HOSTS.has(url.hostname) || databaseName !== DEVELOPMENT_DATABASE_NAME) {
    throw new Error(
      `Seed data can only be applied to the local ${DEVELOPMENT_DATABASE_NAME} database.`,
    )
  }

  return value
}

const users = [
  {
    id: "seed-user-alice",
    name: "アリス",
    bio: "Webセキュリティを学習中です。",
    theme: "dark",
    createdAt: "2026-08-01T00:00:00.000Z",
  },
  {
    id: "seed-user-bob",
    name: "ボブ",
    bio: "コンテナとネットワークが好きです。",
    theme: "light",
    createdAt: "2026-08-02T00:00:00.000Z",
  },
  {
    id: "seed-user-carol",
    name: "キャロル",
    bio: "ログ分析とインシデント対応を勉強しています。",
    theme: "light",
    createdAt: "2026-08-03T00:00:00.000Z",
  },
] as const

const machines = [
  {
    id: "seed-machine-web-auth",
    createdBy: "seed-user-alice",
    name: "Web認証ラボ",
    summary: "ログイン処理を調査し、認証回避の基本を学びます。",
    description:
      "Webアプリケーションのログイン処理に潜む問題を調査し、適切な認証設計を学ぶ公開マシンです。",
    level: "easy",
    systemFlag: "FLAG{seed-web-auth-system}",
    userFlag: "FLAG{seed-web-auth-user}",
    tags: ["Web セキュリティ", "認証・認可"],
    createdAt: "2026-08-04T00:00:00.000Z",
  },
  {
    id: "seed-machine-container-network",
    createdBy: "seed-user-bob",
    name: "コンテナネットワーク調査",
    summary: "コンテナ間通信と公開ポートの設定を調査します。",
    description:
      "コンテナのネットワーク設定を確認し、意図しない通信経路や公開ポートを見つける公開マシンです。",
    level: "medium",
    systemFlag: "FLAG{seed-container-system}",
    userFlag: "",
    tags: ["コンテナ", "ネットワーク"],
    createdAt: "2026-08-08T00:00:00.000Z",
  },
  {
    id: "seed-machine-linux-permissions",
    createdBy: "seed-user-alice",
    name: "Linux権限管理",
    summary: "ファイル所有者と権限設定の不備を調査します。",
    description:
      "Linuxのファイル所有者、グループ、実行権限を確認し、過剰な権限を特定する公開マシンです。",
    level: "easy",
    systemFlag: "FLAG{seed-linux-permissions}",
    userFlag: "",
    tags: ["Linux", "権限管理"],
    createdAt: "2026-08-12T00:00:00.000Z",
  },
  {
    id: "seed-machine-log-trail",
    createdBy: "seed-user-carol",
    name: "ログ追跡演習",
    summary: "複数のログから不審な操作の痕跡を追跡します。",
    description:
      "認証ログとアクセスログを時系列で照合し、インシデントの起点と影響範囲を調査する公開マシンです。",
    level: "medium",
    systemFlag: "",
    userFlag: "FLAG{seed-log-trail}",
    tags: ["ログ分析", "インシデント対応"],
    createdAt: "2026-08-16T00:00:00.000Z",
  },
  {
    id: "seed-machine-api-authorization",
    createdBy: "seed-user-bob",
    name: "API認可チャレンジ",
    summary: "APIの認可設定とリソースへのアクセス経路を検証します。",
    description:
      "利用者ごとのアクセス制御を確認し、認可検証の不足による情報露出を調査する公開マシンです。",
    level: "hard",
    systemFlag: "FLAG{seed-api-authorization-system}",
    userFlag: "FLAG{seed-api-authorization-user}",
    tags: ["API", "認証・認可"],
    createdAt: "2026-08-20T00:00:00.000Z",
  },
  {
    id: "seed-machine-sql-investigation",
    createdBy: "seed-user-carol",
    name: "SQL調査ラボ",
    summary: "入力処理とデータベース権限の問題を調査します。",
    description:
      "アプリケーションの入力処理とデータベース権限を確認し、安全なSQL操作を学ぶ公開マシンです。",
    level: "hard",
    systemFlag: "FLAG{seed-sql-investigation}",
    userFlag: "",
    tags: ["データベース", "入力値検証"],
    createdAt: "2026-08-24T00:00:00.000Z",
  },
] as const

async function main() {
  const pool = new Pool({ connectionString: developmentDatabaseUrl(), max: 1 })
  const client = await pool.connect()

  try {
    await client.query("BEGIN")

    for (const user of users) {
      await client.query(
        `INSERT INTO users
          (id, name, bio, icon_url, theme, profile_completed, created_at, updated_at)
         VALUES ($1, $2, $3, '', $4, true, $5, $5)
         ON CONFLICT (id) DO UPDATE SET
           name = EXCLUDED.name,
           bio = EXCLUDED.bio,
           icon_url = EXCLUDED.icon_url,
           theme = EXCLUDED.theme,
           profile_completed = EXCLUDED.profile_completed,
           created_at = EXCLUDED.created_at,
           updated_at = now()`,
        [user.id, user.name, user.bio, user.theme, user.createdAt],
      )
    }

    for (const machine of machines) {
      await client.query(
        `INSERT INTO machines
          (id, created_by, ai_session_id, name, summary, description, file_path, level,
           published, status, build_progress, system_flag, user_flag, tags, created_at, updated_at)
         VALUES ($1, $2, NULL, $3, $4, $5, '', $6, true, 'ready', 100, $7, $8, $9, $10, $10)
         ON CONFLICT (id) DO UPDATE SET
           created_by = EXCLUDED.created_by,
           ai_session_id = EXCLUDED.ai_session_id,
           name = EXCLUDED.name,
           summary = EXCLUDED.summary,
           description = EXCLUDED.description,
           file_path = EXCLUDED.file_path,
           level = EXCLUDED.level,
           published = EXCLUDED.published,
           status = EXCLUDED.status,
           build_progress = EXCLUDED.build_progress,
           system_flag = EXCLUDED.system_flag,
           user_flag = EXCLUDED.user_flag,
           tags = EXCLUDED.tags,
           error_message = NULL,
           created_at = EXCLUDED.created_at,
           updated_at = now()`,
        [
          machine.id,
          machine.createdBy,
          machine.name,
          machine.summary,
          machine.description,
          machine.level,
          machine.systemFlag,
          machine.userFlag,
          machine.tags,
          machine.createdAt,
        ],
      )
    }

    await client.query("COMMIT")
    console.log(`Seed data applied: ${users.length} users and ${machines.length} machines.`)
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
