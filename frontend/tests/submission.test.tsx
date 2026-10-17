import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useSubmission } from "../src/shared/forms/use-submission";
import { ApiError } from "../src/shared/api/errors";
it("送信の完了前は同期的な再操作も止める", async () => {
  let complete!: () => void;
  const operation = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        complete = resolve;
      }),
  );
  const { result } = renderHook(() => useSubmission(operation));
  act(() => {
    void result.current.submit(new FormData());
    void result.current.submit(new FormData());
  });
  expect(operation).toHaveBeenCalledTimes(1);
  await act(async () => {
    complete();
  });
  expect(result.current.pending).toBe(false);
});
it("応答不明ではエラーを表示して再送を止める", async () => {
  const operation = vi
    .fn()
    .mockRejectedValue(new ApiError(0, "結果を確認してください。", true));
  const { result } = renderHook(() => useSubmission(operation));
  await act(async () => {
    await result.current.submit(new FormData());
  });
  expect(result.current.blocked).toBe(true);
  expect(result.current.error).toContain("結果を確認");
  await act(async () => {
    await result.current.submit(new FormData());
  });
  expect(operation).toHaveBeenCalledTimes(1);
});
it("既知の入力失敗は再操作できる", async () => {
  const operation = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(422, "入力を確認してください。"))
    .mockResolvedValue(undefined);
  const { result } = renderHook(() => useSubmission(operation));
  await act(async () => {
    await result.current.submit(new FormData());
  });
  expect(result.current.blocked).toBe(false);
  await act(async () => {
    await result.current.submit(new FormData());
  });
  await waitFor(() => expect(operation).toHaveBeenCalledTimes(2));
  expect(result.current.error).toBeUndefined();
});
