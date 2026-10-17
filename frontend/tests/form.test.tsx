import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Form, Field } from "../src/shared/ui/common";
it("送信中は二重送信せず失敗後も入力を保持する", async () => {
  const user = userEvent.setup();
  let fail: (e: Error) => void = () => {};
  const submit = vi.fn(
    () =>
      new Promise<void>((_, reject) => {
        fail = reject;
      }),
  );
  render(
    <Form onSubmit={submit}>
      <Field name="name" label="法人名" required />
    </Form>,
  );
  await user.type(screen.getByLabelText(/法人名/), "サンプル法人");
  await user.click(screen.getByRole("button", { name: "登録する" }));
  expect(screen.getByRole("button", { name: "処理中…" })).toBeDisabled();
  fail(new Error("登録できませんでした。"));
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "登録できませんでした。",
    ),
  );
  expect(screen.getByLabelText(/法人名/)).toHaveValue("サンプル法人");
  expect(submit).toHaveBeenCalledTimes(1);
});
