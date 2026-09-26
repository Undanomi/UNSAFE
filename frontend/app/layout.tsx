import type { Metadata } from "next"
import { Inter, Noto_Sans_JP } from "next/font/google"
import "./globals.css"

const inter = Inter({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-inter",
})

const notoSansJp = Noto_Sans_JP({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-noto-sans-jp",
})

export const metadata: Metadata = {
  title: "UNSAFE",
  description: "セキュリティ学習用のシナリオ作成ジェネレーター",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html className={`${inter.variable} ${notoSansJp.variable}`} lang="ja">
      <body>{children}</body>
    </html>
  )
}
