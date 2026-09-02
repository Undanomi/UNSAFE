const PROTECTED_ROUTE_PREFIXES = ["/machines", "/profile", "/users"] as const

export function isProtectedRoute(pathname: string): boolean {
  return PROTECTED_ROUTE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}
