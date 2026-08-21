import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "SLSG | Security Learning Scenario Generator",
  description: "セキュリティ学習用のシナリオ作成ジェネレーター",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  )
}
