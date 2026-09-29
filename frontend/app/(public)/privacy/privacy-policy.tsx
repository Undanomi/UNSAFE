"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"
import { useEffect, useState } from "react"
import { DesignArtwork, MachineListHud } from "@/components/design-artwork"
import { SlsgBrand } from "@/components/slsg-brand"

type PrivacySection = {
  title: string
  body: ReactNode
}

const PRIVACY_SECTIONS: PrivacySection[] = [
  {
    title: "1. 取得する情報",
    body: (
      <>
        <p>
          Googleアカウントでログインする際、Firebase
          Authenticationを通じて、利用者識別子、メールアドレス、表示名、プロフィール画像、認証に必要な情報を取得します。
        </p>
        <p>
          Googleアカウントのパスワードは取得しません。Gmail、Google Drive、Google
          Calendarのデータへのアクセス権限も要求しません。
        </p>
        <p>
          利用者が登録したプロフィール情報、画面表示の設定、マシンの作成内容とチャットへの入力、ビルド履歴、成果物、解答履歴を取り扱います。
        </p>
        <p>
          Firebase
          Authenticationは、認証時のIPアドレスやブラウザ情報を、不正利用の防止などのために取り扱います。本サービスでは、処理に失敗した際のエラーや、マシンのビルドに関する記録を取り扱います。
        </p>
      </>
    ),
  },
  {
    title: "2. 利用目的",
    body: (
      <>
        <p>取得した情報は、次の目的で使用します。</p>
        <ul>
          <li>ログイン、アカウントの作成、プロフィールの表示</li>
          <li>マシンの作成・提供、解答履歴の記録と表示</li>
          <li>お問い合わせへの対応、障害や不正利用の調査</li>
          <li>法令に基づく対応</li>
        </ul>
        <p>
          Googleログインで取得した情報は、認証、アカウントの識別、プロフィールの初期設定に使用します。
        </p>
      </>
    ),
  },
  {
    title: "3. 他の利用者に表示される情報",
    body: (
      <>
        <p>
          ログインしている他の利用者は、あなたのプロフィールを閲覧できます。プロフィールには、表示名、自己紹介、プロフィール画像、作成したマシンと解いたマシンが表示されます。
        </p>
        <p>
          他の利用者に表示されるマシンは、公開設定が有効で、削除済みでないものに限ります。表示名、自己紹介、プロフィール画像、「解いたマシン」の一覧には個別の公開設定がありません。プロフィールへ入力する際は、この表示範囲を踏まえてください。
        </p>
      </>
    ),
  },
  {
    title: "4. 外部サービスへの送信",
    body: (
      <>
        <p>
          認証にはGoogleのFirebase
          Authenticationを利用します。ログインに必要な情報はGoogleに送信され、米国で処理されます。詳しくは
          <a href="https://firebase.google.com/support/privacy" target="_blank" rel="noopener">
            Firebaseの説明
          </a>
          をご確認ください。
        </p>
        <p>
          マシンの生成・検証・修復には、設定に応じてGoogleのGemini
          APIまたはOpenAIのAPIを利用します。利用者が入力したマシンの作成条件やチャットの内容に加え、生成したシナリオ、ソースコード、検証結果、ビルドのエラーやログなどを、処理に必要な範囲で選択された事業者に送信します。
        </p>
        <p>
          Googleログインで取得したメールアドレス、表示名、プロフィール画像、認証用トークンは、マシン生成用の入力として自動で付加しません。ただし、利用者がチャットなどに入力した情報や、生成ファイル・ログに含まれる情報はAI事業者への送信対象になります。実在する個人の情報や、業務で使うパスワード・APIキーなどは入力しないでください。
        </p>
        <p>
          本サービスで利用するGemini
          APIは有料サービスです。Googleは、入力と生成結果をサービスの改善に使用しないと説明しています。一方、不正利用の監視用にはこれらを55日間保存します。詳しくは
          <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noopener">
            Gemini APIの規約
          </a>
          および
          <a
            href="https://ai.google.dev/gemini-api/docs/usage-policies"
            target="_blank"
            rel="noopener"
          >
            不正利用監視の説明
          </a>
          をご確認ください。
        </p>
        <p>
          OpenAIは、APIのデータ共有設定を有効にしない限り、入力と生成結果をモデルの学習に使わないと説明しています。データの保存条件は
          <a
            href="https://developers.openai.com/api/docs/guides/your-data"
            target="_blank"
            rel="noopener"
          >
            OpenAIの説明
          </a>
          をご確認ください。
        </p>
        <p>
          このほか、法令に基づく場合や、不正利用への対応に必要な場合には、必要な範囲で情報を提供することがあります。個人情報の販売や、広告のための提供は行いません。
        </p>
      </>
    ),
  },
  {
    title: "5. 情報の保存と安全管理",
    body: (
      <>
        <p>
          プロフィール、マシン、チャット、解答履歴は本サービスのデータベースに保存します。マシンの作成条件、生成したファイル、検証・修復の記録、ビルド成果物は、AIサーバーやビルドサーバーにも保存します。
        </p>
        <p>
          アカウント情報と、マシン・学習履歴などの関連情報は、アカウントを保有している間保存します。削除を希望する場合の手続は7に記載します。
        </p>
        <p>
          利用者ごとの情報へのアクセスは、ログイン状態と権限を確認して制御します。法令への対応や具体的な不正利用の調査に必要な情報は、その目的に必要な期間保存する場合があります。
        </p>
      </>
    ),
  },
  {
    title: "6. Googleアカウントとの連携解除",
    body: (
      <>
        <p>Googleアカウントの設定画面から、本サービスとの連携を解除できます。</p>
        <p>
          連携を解除しても、本サービスに保存済みのアカウント情報や学習履歴は削除されません。ログイン状態を終了するには本サービスからログアウトしてください。保存済み情報の削除は、7の手続で申請できます。
        </p>
      </>
    ),
  },
  {
    title: "7. 利用者による確認・修正・削除",
    body: (
      <>
        <p>
          ご自身の情報の確認・修正や、アカウントと関連情報の削除を希望する場合は、10のお問い合わせ先へメールでご連絡ください。削除申請は運営者が受け付け、本人確認のうえ対応します。対象となる情報や対応時期は、個別にご案内します。
        </p>
        <p>
          Firebase
          Authenticationの認証情報は、本サービスがFirebase上で削除処理を開始した後も、しばらく残ります。Googleによると、稼働中のシステムとバックアップからの削除には最大180日かかります。詳しくは
          <a href="https://firebase.google.com/support/privacy" target="_blank" rel="noopener">
            Firebaseの説明
          </a>
          をご確認ください。本サービスでの削除後も、外部サービスに送信した情報が各事業者の保存期間中は残る場合があります。
        </p>
        <p>
          OpenAI
          APIへの送信時には、OpenAI側に生成結果を履歴として保存しない設定を使います。ただし、不正利用の監視記録は原則として最大30日間保存され、法令上の必要などにより長く保存される場合があります。詳しくは
          <a
            href="https://developers.openai.com/api/docs/guides/your-data"
            target="_blank"
            rel="noopener"
          >
            OpenAIの説明
          </a>
          をご確認ください。
        </p>
        <p>
          法令により削除に応じられない情報や、調査のために保存が必要な情報がある場合は、その理由と対象をお知らせします。
        </p>
      </>
    ),
  },
  {
    title: "8. Cookieの利用",
    body: (
      <>
        <p>
          本サービスは、ログイン状態を維持するためにCookieを使用します。広告配信や第三者による行動追跡を目的としたCookieは使用しません。
        </p>
        <p>
          ブラウザの設定でCookieを無効にできますが、その場合はログインなど一部の機能を利用できないことがあります。
        </p>
      </>
    ),
  },
  {
    title: "9. 本ポリシーの変更",
    body: (
      <>
        <p>
          サービス内容や情報の取り扱いが変わる場合は、本ページの内容を更新します。重要な変更は、適用前に本ページでお知らせします。
        </p>
        <p>
          Googleログインで取得する情報や、その利用目的を変更する場合は、変更前に内容を説明し、必要な同意を取得します。
        </p>
      </>
    ),
  },
  {
    title: "10. お問い合わせ",
    body: (
      <>
        <p>
          情報の取り扱い、Googleアカウントとの連携解除、アカウント削除に関するお問い合わせは、次の窓口までご連絡ください。
        </p>
        <p>
          メールアドレス：<a href="mailto:slsg@example.com">slsg@example.com</a>
        </p>
      </>
    ),
  },
]

const PRIVACY_TOC_LABELS = [
  "取得する情報",
  "利用目的",
  "公開される情報",
  "外部サービスへの送信",
  "保存と安全管理",
  "連携解除",
  "確認・修正・削除",
  "Cookie",
  "ポリシーの変更",
  "お問い合わせ",
]

function sectionId(index: number) {
  return `privacy-section-${index + 1}`
}

function sectionTitle(title: string) {
  return title.replace(/^\d+\.\s*/, "")
}

function PrivacySectionIndex({ index }: { index: number }) {
  return (
    <span aria-hidden="true" className="slsg-privacy-section-index">
      <svg fill="none" viewBox="0 0 92 100">
        <title>{`セクション${index}`}</title>
        <path className="slsg-privacy-section-index-halo" d="M46 2 85 25v50L46 98 7 75V25Z" />
        <path className="slsg-privacy-section-index-frame" d="M46 4 83 26v48L46 96 9 74V26Z" />
      </svg>
      <strong>{index}</strong>
    </span>
  )
}

export function PrivacyPolicy() {
  const [activeSection, setActiveSection] = useState(1)

  useEffect(() => {
    const sections = PRIVACY_SECTIONS.map((_, index) =>
      document.getElementById(sectionId(index)),
    ).filter((section): section is HTMLElement => section instanceof HTMLElement)
    let frameId: number | null = null

    const updateActiveSection = () => {
      frameId = null

      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) {
        setActiveSection(sections.length)
        return
      }

      const readingLine = Math.min(window.innerHeight * 0.28, 240)
      let nextActiveSection = 1

      for (const [index, section] of sections.entries()) {
        if (section.getBoundingClientRect().top > readingLine) break
        nextActiveSection = index + 1
      }

      setActiveSection((current) => (current === nextActiveSection ? current : nextActiveSection))
    }

    const scheduleActiveSectionUpdate = () => {
      if (frameId !== null) return
      frameId = window.requestAnimationFrame(updateActiveSection)
    }

    updateActiveSection()
    window.addEventListener("scroll", scheduleActiveSectionUpdate, { passive: true })
    window.addEventListener("resize", scheduleActiveSectionUpdate)

    return () => {
      window.removeEventListener("scroll", scheduleActiveSectionUpdate)
      window.removeEventListener("resize", scheduleActiveSectionUpdate)
      if (frameId !== null) window.cancelAnimationFrame(frameId)
    }
  }, [])

  return (
    <div className="slsg-shell slsg-shell-machines slsg-privacy-page">
      <aside className="slsg-sidebar slsg-privacy-sidebar">
        <SlsgBrand className="slsg-privacy-brand" href="/login" />
        <div className="slsg-privacy-sidebar-divider" />
        <Link className="slsg-privacy-login-back" href="/login">
          <ArrowLeft aria-hidden="true" size={18} strokeWidth={1.8} />
          ログイン画面に戻る
        </Link>
        <p className="slsg-privacy-toc-heading">このページの内容</p>
        <nav aria-label="プライバシーポリシーの目次" className="slsg-privacy-toc">
          {PRIVACY_TOC_LABELS.map((label, index) => {
            const itemIndex = index + 1
            const isActive = activeSection === itemIndex
            return (
              <a
                aria-current={isActive ? "location" : undefined}
                className={isActive ? "is-active" : ""}
                href={`#${sectionId(index)}`}
                key={label}
                onClick={() => setActiveSection(itemIndex)}
              >
                <span>{String(itemIndex).padStart(2, "0")}</span>
                <strong>{label}</strong>
              </a>
            )
          })}
        </nav>
      </aside>

      <MachineListHud />
      <DesignArtwork variant="machines" />

      <main className="slsg-main slsg-privacy-main">
        <header className="slsg-privacy-header">
          <Link className="slsg-detail-back-link slsg-privacy-header-back" href="/login">
            <ArrowLeft aria-hidden="true" size={19} strokeWidth={1.8} />
            ログインへ戻る
          </Link>
          <h1 className="slsg-machine-page-title font-bold">プライバシーポリシー</h1>
          <p className="slsg-privacy-updated">最終更新日：2026年9月29日</p>
          <p className="slsg-machine-page-description slsg-muted slsg-privacy-lead">
            UNSAFE（以下「本サービス」）は、セキュリティ学習環境の提供、認証、サービスの安全な運営に必要な範囲で利用者の情報を取り扱います。
          </p>
        </header>

        <article className="slsg-privacy-sections">
          {PRIVACY_SECTIONS.map((section, index) => (
            <section
              className="slsg-privacy-section"
              data-section-index={index + 1}
              id={sectionId(index)}
              key={section.title}
            >
              <PrivacySectionIndex index={index + 1} />
              <div className="slsg-privacy-section-content">
                <h2>{sectionTitle(section.title)}</h2>
                <div className="slsg-privacy-section-body">{section.body}</div>
              </div>
            </section>
          ))}
        </article>
      </main>
    </div>
  )
}
