export function safeReturnPath(path: unknown): string {
  if (typeof path !== "string") return "/admin";
  if (path === "/" || /^\/(admin|stores)(?:\/[a-zA-Z0-9_/-]*)?$/.test(path)) {
    return path;
  }
  return "/admin";
}
