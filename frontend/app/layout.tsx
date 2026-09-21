import type { Metadata } from "next"
import Script from "next/script"
import "./globals.css"

const THEME_BOOTSTRAP_SCRIPT = `
  (function () {
    try {
      var savedTheme = localStorage.getItem("slsg-theme");
      var theme = savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.colorScheme = theme;
    } catch (_) {}
  })();
`

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
    <html lang="ja" suppressHydrationWarning>
      <body>
        {children}
        <Script id="theme-bootstrap" strategy="beforeInteractive">
          {THEME_BOOTSTRAP_SCRIPT}
        </Script>
      </body>
    </html>
  )
}
