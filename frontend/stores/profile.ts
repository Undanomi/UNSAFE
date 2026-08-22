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
  createdMachines: ProfileMachine[]
  solvedMachines: ProfileMachine[]
}

export const PROFILE_DATA: UserProfile = {
  id: "tanaka",
  name: "Tanaka",
  initial: "T",
  bio: "セキュリティ学習シナリオの作成者",
  createdMachines: [
    { id: "nginx-engine", name: "Nginx Engine", createdAt: "2026/7/31" },
    { id: "ssh-basics", name: "SSH Basics", createdAt: "2026/8/7" },
    { id: "docker-lab", name: "Docker Lab", createdAt: "2026/8/12" },
    { id: "linux-permissions", name: "Linux Permissions", createdAt: "2026/8/17" },
    { id: "api-guard", name: "API Guard", createdAt: "2026/8/20" },
  ],
  solvedMachines: [
    { id: "apache-patch", name: "Apache Patch", createdAt: "2026/8/3", solvedAt: "2026/8/9" },
    { id: "log-trail", name: "Log Trail", createdAt: "2026/8/9", solvedAt: "2026/8/15" },
    { id: "ssh-basics", name: "SSH Basics", createdAt: "2026/8/7", solvedAt: "2026/8/17" },
    { id: "docker-lab", name: "Docker Lab", createdAt: "2026/8/12", solvedAt: "2026/8/19" },
    { id: "web-form", name: "Web Form", createdAt: "2026/8/19", solvedAt: "2026/8/20" },
    { id: "sql-lab", name: "SQL Lab", createdAt: "2026/8/16", solvedAt: "2026/8/21" },
    {
      id: "firewall-basics",
      name: "Firewall Basics",
      createdAt: "2026/8/14",
      solvedAt: "2026/8/22",
    },
  ],
}

export const USER_PROFILES: Record<string, UserProfile> = {
  tanaka: PROFILE_DATA,
  suzuki: {
    id: "suzuki",
    name: "Suzuki",
    initial: "S",
    bio: "パッチ管理と脆弱性対応をテーマにした学習マシンを作成しています。",
    createdMachines: [{ id: "apache-patch", name: "Apache Patch", createdAt: "2026/8/3" }],
    solvedMachines: [
      { id: "ssh-basics", name: "SSH Basics", createdAt: "2026/8/7", solvedAt: "2026/8/11" },
    ],
  },
  kato: {
    id: "kato",
    name: "Kato",
    initial: "K",
    bio: "ログ分析を題材に、手を動かして学べるマシンを作成しています。",
    createdMachines: [{ id: "log-trail", name: "Log Trail", createdAt: "2026/8/9" }],
    solvedMachines: [],
  },
  yamamoto: {
    id: "yamamoto",
    name: "Yamamoto",
    initial: "Y",
    bio: "ネットワークの基礎を、設定と観察を通じて学べるマシンを公開しています。",
    createdMachines: [{ id: "firewall-basics", name: "Firewall Basics", createdAt: "2026/8/14" }],
    solvedMachines: [
      { id: "log-trail", name: "Log Trail", createdAt: "2026/8/9", solvedAt: "2026/8/18" },
    ],
  },
  ito: {
    id: "ito",
    name: "Ito",
    initial: "I",
    bio: "データベースとWebアプリケーションの安全な実装をテーマにしています。",
    createdMachines: [
      { id: "sql-lab", name: "SQL Lab", createdAt: "2026/8/16" },
      { id: "web-form", name: "Web Form", createdAt: "2026/8/19" },
    ],
    solvedMachines: [],
  },
}
