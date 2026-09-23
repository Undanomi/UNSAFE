import { ArrowLeft, ShieldCheck } from "lucide-react"
import Link from "next/link"
import type { ReactNode } from "react"

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
          利用者がGoogleアカウントでログインする際、本サービスはFirebase
          Authenticationを通じてGoogleのOAuth 2.0およびOpenID
          Connectを利用し、Googleアカウントを識別するための一意な識別子、メールアドレス、表示名、プロフィール画像および認証に必要な情報を取得します。また、本サービスの認証基盤で発行される利用者識別子やログイン日時を取り扱います。
        </p>
        <p>本サービスは、Googleアカウントのパスワードを取得または保存しません。</p>
        <p>
          Google
          SSOは、ログイン、アカウント識別およびアカウント情報の初期設定のために使用します。Gmail、Google
          Drive、Google
          Calendarなど他のサービスのデータへのアクセス権限は要求せず、これらのデータにはアクセスしません。
        </p>
        <p>
          本サービスは、利用者が登録・入力したプロフィール情報、画面表示設定、セキュリティ学習用マシンの作成内容（チャットへの入力を含みます）、ビルド履歴、成果物および学習履歴を取得します。
        </p>
        <p>
          また、本サービスへのアクセスに伴う情報として、IPアドレス、ブラウザなどの利用環境に関する情報、アクセス日時、操作履歴を取得します。エラー、障害および不正利用の調査に必要なログも、調査に必要な範囲で記録します。
        </p>
      </>
    ),
  },
  {
    title: "2. 利用目的",
    body: (
      <>
        <p>本サービスが1で取得した情報は、以下の目的に必要な範囲で使用します。</p>
        <ul>
          <li>Google SSOによる認証とログイン処理</li>
          <li>利用者のアカウントの作成と識別およびプロフィールの初期設定と表示</li>
          <li>セキュリティ学習環境の作成、提供および管理</li>
          <li>利用状況や学習履歴の表示</li>
          <li>利用者が公開を選択した情報の、選択した範囲での共有</li>
          <li>利用者からのお問い合わせへの対応</li>
          <li>障害の調査およびサービス品質の改善</li>
          <li>不正アクセス、不正利用その他のセキュリティ上の問題の検知と防止</li>
          <li>法令または公的機関からの適法な要請への対応</li>
        </ul>
        <p>
          取得した情報を、上記と無関係な目的には使用しません。Googleログインで取得した情報の利用は、認証、アカウントの作成、識別、初期設定・表示、お問い合わせへの対応、安全管理および法令への対応に必要な範囲に限定します。
        </p>
      </>
    ),
  },
  {
    title: "3. Googleユーザーデータの取り扱い",
    body: (
      <>
        <p>
          本サービスがGoogleログイン（Firebase
          Authentication経由）で取得したGoogleユーザーデータの使用および他のアプリケーションへの提供は、Limited
          Use要件を含む
          <a
            href="https://developers.google.com/terms/api-services-user-data-policy"
            target="_blank"
            rel="noopener"
          >
            Google API Services User Data Policy
          </a>
          に従います。
        </p>
        <p>
          本項は、Googleログインで取得した情報の取り扱いを定めるものです。これらの情報は、2に記載した範囲でのみ使用し、広告配信やAIモデルの学習には使用しません。
        </p>
        <p>
          AIによるマシンの生成・検証・修復に利用する情報と、選択されたAIプロバイダー側での取り扱いについては、4および7に記載します。
        </p>
        <p>
          運営担当者および委託先の担当者がGoogleユーザーデータを閲覧するのは、利用者から対象情報の閲覧について明示的な同意を得たサポート対応、セキュリティ上必要な調査、または法令上必要な場合に限ります。閲覧できる担当者と情報の範囲は、それぞれの対応に必要な最小限に限定します。
        </p>
        <p>
          Googleユーザーデータの第三者への提供は、利用者に明示した本サービスの機能の提供・改善に必要で、利用者の同意を得た場合、セキュリティ上必要かつ法令上認められる場合、または法令に基づく場合に限定します。4に定める場合も、この制限が適用されます。
        </p>
      </>
    ),
  },
  {
    title: "4. 第三者への提供",
    body: (
      <>
        <p>取得した個人情報を、次の場合を除いて第三者へ提供しません。</p>
        <ul>
          <li>提供先、提供する情報および目的を示した上で、利用者から事前に同意を得た場合</li>
          <li>
            本サービスの提供に必要な範囲で、秘密保持、安全管理および委託目的外の利用の禁止を義務付けた委託先へ取り扱いを委託する場合
          </li>
          <li>
            不正利用やセキュリティ上の問題の調査・防止に必要であり、法令上認められる範囲で、対応に必要な相手に必要最小限の情報を提供する場合
          </li>
          <li>法令に基づく場合</li>
        </ul>
        <p>本サービスは、個人情報の販売や、第三者による行動追跡を目的とした提供を行いません。</p>
        <p>
          委託先に提供する場合も、本サービスの提供に必要な最小限の情報に限定し、委託先の取り扱いについて必要かつ適切な監督を行います。認証にはGoogleのFirebase
          Authenticationを利用し、プロフィール、マシン、チャットおよび回答履歴は本サービスが管理するデータベースに保存します。Firebase
          Authenticationでは、認証に伴う情報が米国で処理されます。取り扱いの詳細は
          <a href="https://firebase.google.com/support/privacy" target="_blank" rel="noopener">
            Firebaseのプライバシーとセキュリティに関する説明
          </a>
          をご確認ください。
        </p>
        <p>
          本サービスは、セキュリティ学習用マシンの生成、検証および修復に、運用設定に応じてGoogleのGemini
          APIまたはOpenAIのAPI（GPT-5.6
          Lunaを含みます）のいずれかを利用します。1回の処理で送信する先は、選択されたAIプロバイダーです。この処理のため、チャットなどで入力されたマシン名、学習テーマ、難易度、対象OS、フラグの設定・取得条件を、選択されたAIプロバイダーへ送信します。また、生成したシナリオや攻撃手順、ソースコードおよび設定ファイル、検証結果、ビルド時のエラーメッセージ・ログ、修復履歴、処理対象を識別するシナリオIDを、各処理に応じて送信します。
        </p>
        <p>
          Googleログインで取得したメールアドレス、表示名、プロフィール画像や利用者の認証用トークンを、マシン生成用の入力情報として付加する処理は行いません。ただし、マシンの作成条件に入力された情報や、生成ファイル・ログに含まれた情報は、上記の処理で選択されたAIプロバイダーへの送信対象になります。入力時には、実在する個人の情報や、本番環境のパスワード・APIキーなどの機密情報を含めないでください。
        </p>
        <p>
          Google側の取り扱いについては、
          <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noopener">
            Gemini APIの利用規約
          </a>
          および
          <a
            href="https://ai.google.dev/gemini-api/docs/usage-policies"
            target="_blank"
            rel="noopener"
          >
            不正利用監視に関する説明
          </a>
          もご確認ください。保存については7に記載します。
        </p>
        <p>
          OpenAI側の取り扱いについては、
          <a href="https://openai.com/policies/services-agreement/" target="_blank" rel="noopener">
            OpenAI Services Agreement
          </a>
          および
          <a
            href="https://developers.openai.com/api/docs/guides/your-data"
            target="_blank"
            rel="noopener"
          >
            OpenAI APIのデータ管理に関する説明
          </a>
          もご確認ください。OpenAIの公式説明では、明示的にデータ共有へオプトインしない限り、APIへ送信されたデータはOpenAIのモデルの学習または改善には使用されません。本サービスは、当該データ共有にオプトインしません。保存については7に記載します。
        </p>
        <p>
          利用者がプロフィール、マシンまたは学習履歴の公開を選択した場合は、公開前に対象情報と公開範囲を示し、同意を得た範囲でのみ他の利用者に表示します。
        </p>
      </>
    ),
  },
  {
    title: "5. 情報の保存と安全管理",
    body: (
      <>
        <p>
          本サービスは、取得した情報を不正アクセス、漏えい、改ざん、消失から保護するため、次の対策を講じます。
        </p>
        <ul>
          <li>HTTPSによる通信の暗号化</li>
          <li>保存する個人情報および認証用トークンなどの機密情報の暗号化</li>
          <li>業務上必要な担当者へのアクセス権限の制限</li>
          <li>安全管理に必要な操作ログおよび監査ログの記録</li>
          <li>不要になったトークンの失効および削除</li>
          <li>セキュリティ更新と脆弱性への対応</li>
        </ul>
        <p>
          マシンの作成条件、シナリオおよび処理状況は、本サービスのAIサーバーのデータベースにも保存します。生成したソースコード、検証・修復の記録およびビルド成果物は、本サービスのAIサーバーまたはビルドサーバーの保存領域にも保存します。
        </p>
        <p>
          情報は、利用目的の達成に必要な期間だけ保存します。アカウント情報は原則としてアカウントの利用中に保存し、削除申請後は7に定める手続と期間に従って削除します。
        </p>
        <p>
          法令上の保存義務または具体的な不正利用・セキュリティ上の問題への対応のために保存を継続する場合は、必要な情報と期間に限定し、他の目的には利用しません。保存の必要がなくなり次第削除します。バックアップおよび委託先に保存された情報の削除時期は7に記載します。
        </p>
      </>
    ),
  },
  {
    title: "6. Googleアカウントとの連携解除",
    body: (
      <>
        <p>利用者は、Googleアカウントの設定画面から、本サービスとの連携を解除できます。</p>
        <p>
          連携を解除すると、解除されたアクセス権限に基づいて本サービスがGoogleから新たな情報を取得することはできなくなります。再びGoogleでログインする場合は、改めて連携が必要になることがあります。
        </p>
        <p>
          ただし、連携解除だけでは、保存済みのアカウント情報・学習履歴は削除されません。また、本サービスのログイン状態が直ちに終了するとは限りません。ログイン状態を終了する場合は本サービスからログアウトし、保存済み情報の削除を希望する場合はお問い合わせ窓口から申請してください。
        </p>
        <p>
          連携解除などによりGoogleへのアクセスが不要になり、本サービスがGoogle
          APIへのアクセス用OAuthトークンを保有している場合は、当該トークンを失効させ、削除します。
        </p>
      </>
    ),
  },
  {
    title: "7. 利用者による確認・修正・削除",
    body: (
      <>
        <p>
          利用者は、法令および本サービス所定の手続に従って、保有する個人情報について次の対応を依頼できます。
        </p>
        <ul>
          <li>情報の確認</li>
          <li>誤った情報の修正</li>
          <li>アカウントおよび関連データの削除</li>
          <li>Googleアカウントとの連携解除に関する案内</li>
        </ul>
        <p>
          申請は10のお問い合わせ窓口で受け付けます。第三者による不正な申請を防ぐため、必要な範囲で本人確認を行います。
        </p>
        <p>
          削除申請を受け付け、本人確認を完了した後、速やかに本サービスでの対象情報の削除および委託先への削除依頼を行います。処理に時間を要する場合は、その理由と完了予定時期をお知らせします。ただし、5に定める保存が必要な情報は除きます。
        </p>
        <p>
          本サービスが管理するバックアップ内の対象情報は、通常利用を停止したうえで削除します。Firebase
          Authenticationに保存された認証情報は、本サービスが同サービス上で対象利用者の削除処理を開始した後、稼働中のシステムおよびバックアップからの削除に最大180日かかります。詳細は
          <a href="https://firebase.google.com/support/privacy" target="_blank" rel="noopener">
            Firebaseのデータ処理に関する説明
          </a>
          をご確認ください。
        </p>
        <p>
          Gemini
          APIへ送信した入力情報、付随する文脈情報および生成結果は、Googleの標準の不正利用監視において、不正利用の検知・防止および必要な法令対応のため55日間保存されます。必要に応じて、Googleの権限を持つ担当者が確認する場合があります。この保存期間はFirebase
          Authenticationの保存期間とは別です。本サービスでのデータ削除が、Google側の監視用記録の即時削除を意味するものではありません。詳細は
          <a
            href="https://ai.google.dev/gemini-api/docs/usage-policies"
            target="_blank"
            rel="noopener"
          >
            Gemini APIの不正利用監視に関する説明
          </a>
          をご確認ください。
        </p>
        <p>
          OpenAI APIへ送信するリクエストには、生成結果をResponses
          APIのアプリケーション状態として保存しない設定（
          <code>store: false</code>
          ）を使用します。ただし、通常のAPI利用では、入力情報、生成結果およびこれらから得られるメタデータが、不正利用の検知・防止および必要な法令対応のための監視ログに含まれ、最大30日間保存される場合があります。また、暗号化されたプロンプトキャッシュが最大24時間保持される場合があります。OpenAIとの契約またはプロジェクトにZero
          Data RetentionもしくはModified Abuse
          Monitoringが適用される場合は、保存条件が異なることがあります。本サービスでのデータ削除が、OpenAI側の監視用記録またはキャッシュの即時削除を意味するものではありません。詳細は
          <a
            href="https://developers.openai.com/api/docs/guides/your-data"
            target="_blank"
            rel="noopener"
          >
            OpenAI APIのデータ管理に関する説明
          </a>
          をご確認ください。
        </p>
        <p>
          削除を完了した場合はその旨を通知します。対応できない場合や一部の情報を保存する必要がある場合は、法令上可能な範囲で、その理由、対象情報および保存期間または保存終了の条件をお知らせします。
        </p>
      </>
    ),
  },
  {
    title: "8. Cookieの利用",
    body: (
      <>
        <p>
          本サービスは、ログイン状態の維持、認証処理、不正利用の防止のためにCookieを使用します。広告配信や第三者による行動追跡を目的としたCookieは使用しません。
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
          本ポリシーは、サービス内容や法令などの変更に応じて改定することがあります。このプライバシーポリシーに基づく利用者の権利を利用者の明示的な同意なく縮小することはありません。本ページにポリシーの変更内容と改定日を掲載し、過去の内容も確認できるようにします。
        </p>
        <p>
          重要な変更を行う場合は、変更の適用前に利用者へ通知し、法令上必要な場合は改めて同意を取得します。Googleユーザーデータについて、従来説明していなかった情報を取得する場合や、新たな目的・方法で利用する場合は、その取得・利用を開始する前に変更内容を説明し、利用者の同意を取得します。
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
              <p className="mt-4 text-[0.9rem] text-[#aaa89f]">最終更新日：2026年9月23日</p>
            </div>
          </div>

          <div className="mt-10 grid gap-10 text-[1rem] leading-8 text-[#d3d1ca]">
            <p>
              Security Learning Scenario
              Generator（以下「本サービス」）は、セキュリティ学習環境の提供、認証、サービスの安全な運営に必要な範囲で利用者の情報を取り扱います。
            </p>

            {PRIVACY_SECTIONS.map((section) => (
              <section key={section.title}>
                <h2 className="text-[1.3rem] leading-7 font-semibold tracking-[-0.025em] text-[#f3f1ea]">
                  {section.title}
                </h2>
                <div className="mt-3 space-y-5 [&_a]:underline [&_a]:underline-offset-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6">
                  {section.body}
                </div>
              </section>
            ))}
          </div>
        </article>
      </div>
    </main>
  )
}
