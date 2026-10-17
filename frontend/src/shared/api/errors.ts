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
