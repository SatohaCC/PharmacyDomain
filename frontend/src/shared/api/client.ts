import createClient from "openapi-fetch";
import type { components, paths } from "./schema";
import { accessToken } from "../auth/session";
export type Actor = components["schemas"]["CurrentActorDto"];
export const api = createClient<paths>({ baseUrl: "/api" });
api.use({
  onRequest({ request }) {
    const token = accessToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
});
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public uncertain = false,
  ) {
    super(message);
  }
}
export function errorText(error: unknown): string {
  if (error instanceof ApiError)
    return (
      error.message ||
      ({
        401: "再ログインしてください。",
        403: "操作する権限がありません。",
        404: "対象が見つかりません。",
        409: "競合が発生しました。状態を確認してください。",
        422: "入力内容を確認してください。",
      }[error.status] ??
        "サーバーでエラーが発生しました。")
    );
  return error instanceof Error ? error.message : "処理できませんでした。";
}
export async function result<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let res;
  try {
    res = await request;
  } catch {
    throw new ApiError(
      0,
      "通信が途切れました。書き込みの結果を確認してから操作してください。",
      true,
    );
  }
  if (!res.response.ok) {
    const e = res.error as { message?: unknown; errors?: unknown };
    throw new ApiError(
      res.response.status,
      typeof e?.message === "string" ? e.message : "",
      res.response.status >= 500,
    );
  }
  return res.data as T;
}
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
export function corporationParams(corporateId: string) {
  return { path: { corporate_id: corporateId } };
}
