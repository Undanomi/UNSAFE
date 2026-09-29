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
  metadataBase: new URL("https://unsafe.konekotech.com"),
  title: "UNSAFE",
  description: "セキュリティ学習用の演習環境を自動作成するアプリケーション",
  icons: {
    icon: { url: "/logo.png", type: "image/png", sizes: "1254x1254" },
    apple: { url: "/logo.png", type: "image/png" },
  },
  openGraph: {
    images: [{ url: "/thumb-share.png", width: 1926, height: 816, alt: "UNSAFE" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/thumb-share.png"],
  },
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
