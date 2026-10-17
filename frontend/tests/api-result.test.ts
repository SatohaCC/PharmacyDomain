import { expect, it } from "vitest";
import { ApiError, result } from "../src/shared/api/errors";
it("成功のデータを返す", async () => {
  await expect(
    result(
      Promise.resolve({
        data: { id: "example" },
        response: new Response(null, { status: 201 }),
      }),
    ),
  ).resolves.toEqual({ id: "example" });
});
it.each([
  [422, false],
  [409, false],
  [500, true],
])("HTTP%sを再送可否とともに分類する", async (status, uncertain) => {
  try {
    await result(
      Promise.resolve({
        error: { message: "確認してください。" },
        response: new Response(null, { status }),
      }),
    );
    throw new Error("成功として扱われました。");
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status,
      uncertain,
      message: "確認してください。",
    });
  }
});
it("通信切断を応答不明にする", async () => {
  await expect(
    result(Promise.reject(new TypeError("切断"))),
  ).rejects.toMatchObject({ status: 0, uncertain: true });
});
