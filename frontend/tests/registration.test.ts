import { expect, it, vi } from "vitest";
import {
  prepareRegistration,
  type RegistrationProgress,
} from "../src/features/users/model/prepare-registration";
it("登録失敗後は本人を重複登録せず再試行する", async () => {
  const createPerson = vi.fn().mockResolvedValue("person-1");
  const register = vi
    .fn()
    .mockRejectedValueOnce(new Error("競合"))
    .mockResolvedValue({ id: "register-1", login_id: "test-admin" });
  const progress: RegistrationProgress = {};
  await expect(
    prepareRegistration(progress, { createPerson, register }, () => {}),
  ).rejects.toThrow("競合");
  expect(progress.personId).toBe("person-1");
  await prepareRegistration(progress, { createPerson, register }, () => {});
  expect(createPerson).toHaveBeenCalledTimes(1);
  expect(register).toHaveBeenCalledTimes(2);
});
it("通信結果不明時は再送を止める", async () => {
  const progress: RegistrationProgress = {};
  const createPerson = vi.fn().mockRejectedValue(new TypeError("通信切断"));
  const register = vi.fn();
  await expect(
    prepareRegistration(progress, { createPerson, register }, () => {}),
  ).rejects.toThrow();
  await expect(
    prepareRegistration(progress, { createPerson, register }, () => {}),
  ).rejects.toThrow("結果を確認");
  expect(createPerson).toHaveBeenCalledTimes(1);
});
