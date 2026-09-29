import Image from "next/image"
import Link from "next/link"

type SlsgBrandProps = {
  href?: string
  className?: string
  variant?: "compact" | "orbit"
}

export function UnsafeBrandSymbol({ className = "" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={`slsg-brand-symbol ${className}`}
      fill="none"
      viewBox="0 0 32 32"
    >
      <path className="slsg-brand-symbol-frame" d="M16 3 27 9.4v13.2L16 29 5 22.6V9.4L16 3Z" />
      <path
        className="slsg-brand-symbol-letter"
        d="M10.4 10.2v6.2c0 3.4 2 5.4 5.6 5.4s5.6-2 5.6-5.4v-6.2"
      />
    </svg>
  )
}

export function SlsgBrand({
  href = "/machines",
  className = "",
  variant = "compact",
}: SlsgBrandProps) {
  return (
    <Link
      aria-label="UNSAFE マシン一覧へ"
      className={`slsg-brand slsg-brand-${variant} ${className}`}
      href={href}
    >
      <Image
        alt=""
        className="slsg-brand-image"
        height={816}
        preload
        sizes="240px"
        src="/thumb.png"
        width={1926}
      />
    </Link>
  )
}
