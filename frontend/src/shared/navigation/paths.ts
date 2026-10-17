export function safeReturnPath(path: unknown): string {
  if (typeof path !== "string") return "/admin";
  if (path === "/invitations/accept") return path;
  return /^\/admin(?:\/[a-zA-Z0-9_/-]*)?$/.test(path) ? path : "/admin";
}
export function readInvitation(): string {
  const secret =
    new URLSearchParams(location.hash.slice(1)).get("secret") || "";
  if (location.hash)
    history.replaceState(null, "", location.pathname + location.search);
  return secret;
}
