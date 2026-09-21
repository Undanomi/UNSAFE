import { checkDatabaseConnection } from "@/lib/database/client"

export async function GET() {
  try {
    await checkDatabaseConnection()
    return Response.json({ status: "ready" })
  } catch (error) {
    console.error("PostgreSQL readiness check failed.", error)
    return Response.json({ status: "unavailable" }, { status: 503 })
  }
}
