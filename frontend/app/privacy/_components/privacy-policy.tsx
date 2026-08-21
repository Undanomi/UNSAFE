import { ArrowLeft, ShieldCheck } from "lucide-react"
import Link from "next/link"

const sections = [
  {
    body: "SLSG は、セキュリティ学習用マシンの作成・利用に必要な範囲で情報を取り扱います。",
    title: "1. 取得する情報",
  },
  {
    body: "アカウント情報、プロフィール情報、マシンの作成内容、学習履歴を取り扱います。Google アカウントでログインする場合は、認証に必要な基本プロフィール情報を取得します。",
    title: "2. 利用目的",
  },
  {
    body: "取得した情報は、アカウントの識別、学習環境の提供、サービスの改善、不正利用の防止に利用します。広告配信を目的とした第三者提供は行いません。",
    title: "3. 情報の共有",
  },
  {
    body: "利用者は、法令およびサービス上の手続に従って、保有するアカウント情報の確認・修正・削除を依頼できます。",
    title: "4. 利用者の選択",
  },
  {
    body: "本ポリシーを変更する場合は、このページで内容と改定日を公開します。重要な変更がある場合は、サービス内でもお知らせします。",
    title: "5. 改定",
  },
]

export function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-[#151513] px-5 py-8 text-[#e7e5df] sm:px-8 sm:py-12">
      <div className="mx-auto max-w-3xl">
        <Link
          className="inline-flex items-center gap-2 text-[0.86rem] font-bold text-[#bdbbb3] transition hover:text-white"
          href="/login"
        >
          <ArrowLeft aria-hidden="true" size={17} strokeWidth={2} />
          ログインへ戻る
        </Link>

        <article className="mt-14">
          <div className="flex items-start gap-4 border-b border-[#3a3934] pb-9">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl border border-[#4b4a43] bg-[#20201e] text-[#e7e5df]">
              <ShieldCheck aria-hidden="true" size={23} strokeWidth={1.8} />
            </span>
            <div>
              <p className="text-[0.78rem] font-bold tracking-[0.08em] text-[#aaa89f]">SLSG</p>
              <h1 className="mt-2 text-[clamp(2.2rem,7vw,4.5rem)] leading-[1.02] font-semibold tracking-[-0.05em]">
                プライバシーポリシー
              </h1>
              <p className="mt-4 text-[0.9rem] text-[#aaa89f]">最終更新日: 2026年8月22日</p>
            </div>
          </div>

          <div className="mt-10 grid gap-10 text-[1rem] leading-8 text-[#d3d1ca]">
            <p>
              このプライバシーポリシーは、SLSG
              が利用者の情報をどのように取り扱うかを説明するものです。
            </p>

            <blockquote className="border-l-2 border-[#8b8980] pl-5 text-[#bdbbb3]">
              必要な情報だけを取得し、学習環境の提供以外の目的では利用しません。
            </blockquote>

            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-[1.3rem] leading-7 font-semibold tracking-[-0.025em] text-[#f3f1ea]">
                  {section.title}
                </h2>
                <p className="mt-3">{section.body}</p>
              </section>
            ))}

            <section>
              <h2 className="text-[1.3rem] leading-7 font-semibold tracking-[-0.025em] text-[#f3f1ea]">
                6. お問い合わせ
              </h2>
              <p className="mt-3">
                情報の取り扱いに関するお問い合わせは、サービス運営者までご連絡ください。
              </p>
              <code className="mt-4 inline-block rounded-lg border border-[#3a3934] bg-[#20201e] px-3 py-1.5 text-[0.86rem] text-[#d3d1ca]">
                privacy@slsg.example
              </code>
            </section>
          </div>
        </article>
      </div>
    </main>
  )
}
