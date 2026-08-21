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

export const machineList: MachineSummary[] = [
  {
    id: "nginx-engine",
    name: "Nginx Engine",
    summary: "Nginx の設定とログから、公開範囲の設定不備を調査します。",
    description:
      "Nginx の設定ファイルとアクセスログを調査し、意図せず公開されているリソースを特定する学習用マシンです。公開範囲の設定不備がサービスへ与える影響を確認します。",
    author: "Tanaka",
    authorId: "tanaka",
    createdAt: "2026/7/31",
    visibility: "非公開",
    isOwned: true,
    theme: "Web サーバーの設定不備",
    difficulty: "Easy",
  },
  {
    id: "apache-patch",
    name: "Apache Patch",
    summary: "公開コンポーネントのパッチ適用状況から、脆弱性リスクを調査します。",
    description:
      "公開中のApacheコンポーネントとパッチ適用状況を照合し、既知の脆弱性によるリスクを調査する学習用マシンです。更新計画と影響範囲を整理します。",
    author: "Suzuki",
    authorId: "suzuki",
    createdAt: "2026/8/3",
    visibility: "公開",
    isOwned: false,
    theme: "パッチ適用と脆弱性管理",
    difficulty: "Medium",
  },
  {
    id: "ssh-basics",
    name: "SSH Basics",
    summary: "鍵認証とアクセス制御の基本設定を通して、SSH を学びます。",
    description:
      "SSHの基本設定を確認し、鍵認証とアクセス制御の考え方を学ぶ入門用マシンです。安全な接続設定と不要なアクセスを抑える方法を確認します。",
    author: "Tanaka",
    authorId: "tanaka",
    createdAt: "2026/8/7",
    visibility: "公開",
    isOwned: true,
    theme: "認証とアクセス制御",
    difficulty: "Very Easy",
  },
  {
    id: "log-trail",
    name: "Log Trail",
    summary: "ログの時系列をたどり、不審な操作の痕跡を見つけます。",
    description:
      "複数のログを時系列でたどり、不審な操作の起点と影響範囲を調査する学習用マシンです。ログの相関からインシデント対応の基礎を身に付けます。",
    author: "Kato",
    authorId: "kato",
    createdAt: "2026/8/9",
    visibility: "公開",
    isOwned: false,
    theme: "ログ調査",
    difficulty: "Medium",
  },
  {
    id: "docker-lab",
    name: "Docker Lab",
    summary: "コンテナの設定と実行環境を確認し、基本的な運用を学びます。",
    description:
      "Dockerコンテナの設定と実行環境を確認し、隔離範囲や公開ポートを調査する学習用マシンです。安全なコンテナ運用の基本を学びます。",
    author: "Tanaka",
    authorId: "tanaka",
    createdAt: "2026/8/12",
    visibility: "非公開",
    isOwned: true,
    theme: "コンテナの基礎",
    difficulty: "Easy",
  },
  {
    id: "firewall-basics",
    name: "Firewall Basics",
    summary: "ファイアウォールのルールを確認し、通信制御の基本を学びます。",
    description:
      "ファイアウォールのルールと通信要件を照合し、不要に開放された経路を見つける学習用マシンです。最小権限によるネットワーク制御を確認します。",
    author: "Yamamoto",
    authorId: "yamamoto",
    createdAt: "2026/8/14",
    visibility: "公開",
    isOwned: false,
    theme: "ネットワーク制御",
    difficulty: "Easy",
  },
  {
    id: "sql-lab",
    name: "SQL Lab",
    summary: "安全なSQL操作と、データベースの基本的な保護を学びます。",
    description:
      "データベースの操作ログと入力処理を確認し、安全なSQL操作を学ぶ学習用マシンです。入力値検証と権限設定による基本的な保護を整理します。",
    author: "Ito",
    authorId: "ito",
    createdAt: "2026/8/16",
    visibility: "公開",
    isOwned: false,
    theme: "データベースの基礎",
    difficulty: "Medium",
  },
  {
    id: "linux-permissions",
    name: "Linux Permissions",
    summary: "Linux の所有者・権限設定を確認し、アクセス制御を学びます。",
    description:
      "Linuxのファイル所有者とアクセス権を調査し、過剰な権限を見つける学習用マシンです。ユーザー、グループ、実行権限を用いたアクセス制御を学びます。",
    author: "Tanaka",
    authorId: "tanaka",
    createdAt: "2026/8/17",
    visibility: "公開",
    isOwned: true,
    theme: "権限管理",
    difficulty: "Easy",
  },
  {
    id: "network-trace",
    name: "Network Trace",
    summary: "通信記録を解析し、ネットワーク上の異常を追跡します。",
    description:
      "パケット記録と通信ログを解析し、ネットワーク上の異常な挙動を追跡する学習用マシンです。通信先、ポート、時系列の関係を確認します。",
    author: "Suzuki",
    authorId: "suzuki",
    createdAt: "2026/8/18",
    visibility: "公開",
    isOwned: false,
    theme: "通信解析",
    difficulty: "Medium",
  },
  {
    id: "web-form",
    name: "Web Form",
    summary: "フォーム入力を検証し、安全なWebアプリケーション実装を学びます。",
    description:
      "Webフォームの入力処理を確認し、検証漏れによるリスクを調査する学習用マシンです。サーバー側検証と安全なエラーハンドリングの基本を学びます。",
    author: "Ito",
    authorId: "ito",
    createdAt: "2026/8/19",
    visibility: "公開",
    isOwned: false,
    theme: "入力値の検証",
    difficulty: "Easy",
  },
  {
    id: "api-guard",
    name: "API Guard",
    summary: "API の認可設定を確認し、アクセス制御の不備を調査します。",
    description:
      "APIの認可設定とリソースへのアクセス経路を確認し、権限不足の検証を調査する学習用マシンです。利用者ごとのアクセス制御を見直します。",
    author: "Tanaka",
    authorId: "tanaka",
    createdAt: "2026/8/20",
    visibility: "非公開",
    isOwned: true,
    theme: "API の認可",
    difficulty: "High",
  },
  {
    id: "crypto-intro",
    name: "Crypto Intro",
    summary: "暗号化の基本と、データを保護するための考え方を学びます。",
    description:
      "保存データと通信データの暗号化方式を確認し、暗号化の基本を学ぶ入門用マシンです。鍵の取り扱いと適切な暗号方式の選択を整理します。",
    author: "Suzuki",
    authorId: "suzuki",
    createdAt: "2026/8/21",
    visibility: "公開",
    isOwned: false,
    theme: "暗号化の基礎",
    difficulty: "Very Easy",
  },
]
