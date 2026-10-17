import { expect, it, vi } from "vitest";
import {
  prepareInvitation,
  type RegistrationProgress,
} from "../src/features/users/registration";
it("招待失敗後は本人を重複登録せず再試行する", async () => {
  const createPerson = vi.fn().mockResolvedValue("person-1");
  const invite = vi
    .fn()
    .mockRejectedValueOnce(new Error("競合"))
    .mockResolvedValue({ id: "invite-1", secret: "secret" });
  const progress: RegistrationProgress = {};
  await expect(
    prepareInvitation(progress, { createPerson, invite }, () => {}),
  ).rejects.toThrow("競合");
  expect(progress.personId).toBe("person-1");
  await prepareInvitation(progress, { createPerson, invite }, () => {});
  expect(createPerson).toHaveBeenCalledTimes(1);
  expect(invite).toHaveBeenCalledTimes(2);
});
it("通信結果不明時は再送を止める", async () => {
  const progress: RegistrationProgress = {};
  const createPerson = vi.fn().mockRejectedValue(new TypeError("通信切断"));
  const invite = vi.fn();
  await expect(
    prepareInvitation(progress, { createPerson, invite }, () => {}),
  ).rejects.toThrow();
  await expect(
    prepareInvitation(progress, { createPerson, invite }, () => {}),
  ).rejects.toThrow("結果を確認");
  expect(createPerson).toHaveBeenCalledTimes(1);
});
