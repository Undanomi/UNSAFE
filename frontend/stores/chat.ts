export const CHAT_STEPS = {
  machineName: 1,
  visibility: 2,
  theme: 3,
  difficulty: 4,
  userFlagChoice: 5,
  userFlagDetails: 6,
  systemFlagChoice: 7,
  systemFlagDetails: 8,
  complete: 9,
} as const

export const CHAT_CONFIG = {
  machineNameMinLength: 1,
  machineNameMaxLength: 40,
  newChatPath: "/machines/chat",
  progressMinimum: 0,
  progressPercentage: 100,
  stepIncrement: 1,
} as const

export const VISIBILITY_OPTIONS = ["非公開", "公開"] as const
export const DIFFICULTY_OPTIONS = ["Very Easy", "Easy", "Medium", "High"] as const
export const SCENARIO_PROMPT_SUGGESTIONS = [
  "公開Webサービスの設定不備を調査し、初期侵入から権限昇格までを学べるシナリオにしてください。",
  "不審なアクセスログを手掛かりに侵害経路を特定し、証拠とフラグを回収するシナリオにしてください。",
  "認証・認可の不備を悪用して一般ユーザー権限を得るシナリオにしてください。",
  "ネットワークサービスを列挙し、複数の弱点を組み合わせて攻略するシナリオにしてください。",
] as const

export type ChatVisibility = (typeof VISIBILITY_OPTIONS)[number]
export type ChatDifficulty = (typeof DIFFICULTY_OPTIONS)[number]

export type ChatSession = {
  id: string
  name: string
  status: "入力中" | "基本設定完了"
  initialStep: number
  initialAnswers?: Partial<ChatAnswers>
  creationStatus: ChatCreationStatus
  creationFailure: ChatCreationFailure | null
  machineId: string | null
}

export type ChatCreationFailure = {
  kind: "ai_safety_refusal" | "settings" | "system"
  summary: string
  suggestions: string[]
}

export type ChatCreationStatus =
  | "input"
  | "generating_scenario"
  | "building"
  | "completed"
  | "failed"
  | "cancelled"
export type ChatSessionSummary = Pick<ChatSession, "id" | "name" | "status">

export type ChatAnswers = {
  name: string
  visibility: ChatVisibility | ""
  theme: string
  difficulty: ChatDifficulty | ""
  needsUserFlag: boolean | null
  userFlagDetails: string
  needsSystemFlag: boolean | null
  systemFlagDetails: string
}

export const EMPTY_CHAT_ANSWERS: ChatAnswers = {
  name: "",
  visibility: "",
  theme: "",
  difficulty: "",
  needsUserFlag: null,
  userFlagDetails: "",
  needsSystemFlag: null,
  systemFlagDetails: "",
}

export const CHAT_COPY = {
  assistantLabel: "AI",
  basicReadyPrompt: {
    help: "フラグを指定しない場合は、AIがシナリオに合わせて自動設定します。",
    question: "基本設定がそろいました。マシンを作成しますか？",
  },
  buttons: {
    createBasic: "マシンを作成",
    createComplete: "マシンを作成",
    continueDetails: "設定を続ける",
    next: "次へ進む",
    setBasic: "次へ進む",
  },
  completePrompt: {
    help: "",
    question: "設定がそろいました。内容を確認してマシンを作成してください。",
  },
  errors: {
    answerRequired: "この質問への回答を入力または選択してください。",
    machineName: `マシン名を${CHAT_CONFIG.machineNameMinLength}〜${CHAT_CONFIG.machineNameMaxLength}文字で入力してください。`,
  },
  fields: {
    machineName: `マシン名（${CHAT_CONFIG.machineNameMaxLength}文字まで）`,
    machineNamePlaceholder: "例: Nginx Engine",
    systemFlagDetails: "システムフラグの取得条件",
    systemFlagDetailsPlaceholder: "権限や必要な操作を詳しく入力してください。",
    scenarioPrompt: "作成したいシナリオの要望（500文字まで）",
    scenarioPromptPlaceholder:
      "例: 社内ポータルの設定不備を調査し、Webから初期侵入して権限昇格まで学べるシナリオにしてください。",
    userFlagDetails: "ユーザーフラグの取得条件",
    userFlagDetailsPlaceholder: "配置場所や入手までの条件を詳しく入力してください。",
  },
  missingSession: {
    action: "新しいチャットを開始",
    message: "チャット一覧から新規作成または既存の会話を選択してください。",
    title: "この作成チャットは見つかりませんでした。",
  },
  progress: "STEP",
  summary: {
    empty: "未入力",
    labels: {
      difficulty: "難易度",
      machineName: "マシン名",
      systemFlag: "システムフラグ",
      theme: "シナリオの要望",
      userFlag: "ユーザーフラグ",
      visibility: "公開範囲",
    },
    title: "入力内容の概要",
  },
  userLabel: "あなた",
  yesNo: {
    no: "いいえ、用意しない",
    yes: "はい、用意する",
  },
} as const

export const CHAT_PROMPTS: Record<number, { help: string; question: string }> = {
  [CHAT_STEPS.machineName]: {
    help: `一覧で見分けやすい名前を、${CHAT_CONFIG.machineNameMaxLength}文字以内で付けてください。`,
    question: "マシン名を入力してください。",
  },
  [CHAT_STEPS.visibility]: {
    help: "",
    question: "公開範囲を教えてください。",
  },
  [CHAT_STEPS.theme]: {
    help: "例文を選ぶか、作りたい内容を文章で自由に入力してください。タグは完成したシナリオからAIが自動で生成します。",
    question: "どのようなシナリオのマシンを作成しますか？",
  },
  [CHAT_STEPS.difficulty]: {
    help: "ここまでで基本設定が完了します。",
    question: "難易度を入力してください。",
  },
  [CHAT_STEPS.userFlagChoice]: {
    help: "「いいえ」を選んだ場合は、詳細入力を省略できます。",
    question: "ユーザーフラグを用意しますか？",
  },
  [CHAT_STEPS.userFlagDetails]: {
    help: "あとから学習者が取り組めるよう、条件を具体的に書いてください。",
    question: "ユーザーフラグを取得するのに必要な情報を、できる限り詳細に入力してください。",
  },
  [CHAT_STEPS.systemFlagChoice]: {
    help: "「いいえ」を選んだ場合は、詳細入力を省略できます。",
    question: "システムフラグを用意しますか？",
  },
  [CHAT_STEPS.systemFlagDetails]: {
    help: "あとから学習者が取り組めるよう、条件を具体的に書いてください。",
    question: "システムフラグを取得するのに必要な情報を、できる限り詳細に入力してください。",
  },
}

export const NEW_CHAT_SESSION: ChatSession = {
  id: "session-new",
  name: "マシン作成",
  status: "入力中",
  initialStep: CHAT_STEPS.machineName,
  creationStatus: "input",
  creationFailure: null,
  machineId: null,
}
