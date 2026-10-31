export function safeReturnPath(path: unknown): string {
  if (typeof path !== "string") return "/admin";
  return /^\/admin(?:\/[a-zA-Z0-9_/-]*)?$/.test(path) ? path : "/admin";
}
