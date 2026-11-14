export function safeReturnPath(
  path: unknown,
  options: {
    fallbackPath: string;
    allowedPrefixes: readonly string[];
  },
): string {
  if (typeof path !== "string") return options.fallbackPath;
  if (path === "/") return path;
  for (const prefix of options.allowedPrefixes) {
    if (
      path === prefix ||
      (path.startsWith(`${prefix}/`) &&
        /^[a-zA-Z0-9_/-]*$/.test(path.slice(prefix.length + 1)))
    ) {
      return path;
    }
  }
  return options.fallbackPath;
}
