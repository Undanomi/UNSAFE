import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: {
    /* サイドバーのアイコンと重なっていたため右下に移動 */
    position: "bottom-right",
  },
}

export default nextConfig
