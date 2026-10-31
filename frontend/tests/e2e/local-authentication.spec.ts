import { test, expect } from "@playwright/test";

test("初期パスワードでは変更画面へ進みパスワードと制限トークンを保存せず利用開始する", async ({
  page,
}) => {
  let meCalls = 0;
  await page.route("**/api/auth/login", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      corporate_id: "test-corporate",
      email: "test-admin@example.test",
      password: "test-initial-password-12345",
    });
    await route.fulfill({
      json: {
        access_token: "restricted-test-token",
        password_change_required: true,
      },
    });
  });
  await page.route("**/api/auth/password", async (route) => {
    expect(route.request().headers().authorization).toBe(
      "Bearer restricted-test-token",
    );
    expect(route.request().postDataJSON()).toEqual({
      password: "test-changed-password-67890",
    });
    await route.fulfill({
      json: {
        access_token: "normal-test-token",
        password_change_required: false,
      },
    });
  });
  await page.route("**/api/me/stores", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/me", async (route) => {
    meCalls++;
    expect(route.request().headers().authorization).toBe(
      "Bearer normal-test-token",
    );
    await route.fulfill({
      json: {
        person_id: "test-person",
        account_id: "test-account",
        membership_id: "test-membership",
        corporate_id: "test-corporate",
        roles: ["corporate_admin"],
        staff_id: null,
        store_ids: [],
      },
    });
  });
  await page.route("**/api/corporates/test-corporate", (route) =>
    route.fulfill({
      json: {
        id: "test-corporate",
        name: "テスト薬局グループ",
        representative_name: "テスト 太郎",
        is_active: true,
      },
    }),
  );
  await page.goto("/login");
  await page.getByLabel("法人ID").fill("test-corporate");
  await page.getByLabel("メールアドレス").fill("test-admin@example.test");
  await page
    .getByLabel(/^パスワード(?:必須| 必須)?$/)
    .fill("test-initial-password-12345");
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "初回パスワード変更" }),
  ).toBeVisible();
  expect(meCalls).toBe(0);
  await expect(
    page.getByLabel(/^新しいパスワード(?:必須| 必須)?$/),
  ).toHaveValue("");
  await page
    .getByLabel(/^新しいパスワード(?:必須| 必須)?$/)
    .fill("test-changed-password-67890");
  await page
    .getByLabel("新しいパスワード（確認）")
    .fill("test-changed-password-67890");
  await page
    .getByRole("button", { name: "パスワードを変更して利用開始" })
    .click();
  await expect(
    page.getByRole("heading", { name: "テスト薬局グループ" }),
  ).toBeVisible();
  expect(meCalls).toBeGreaterThan(0);
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toMatch(/restricted-test-token|password-12345|password-67890/);
  expect(page.url()).not.toMatch(/token|password/);
  await page.screenshot({
    path: "test-results/local-authentication-completed.png",
    fullPage: true,
  });
});

test("ログイン失敗では管理画面へ進まない", async ({ page }) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 401,
      json: {
        code: "LOGIN_FAILED",
        message: "メールアドレスまたはパスワードを確認してください。",
        errors: [],
      },
    }),
  );
  await page.goto("/login");
  await page.getByLabel("法人ID").fill("test-corporate");
  await page.getByLabel("メールアドレス").fill("test-admin@example.test");
  await page
    .getByLabel(/^パスワード(?:必須| 必須)?$/)
    .fill("test-wrong-password");
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "メールアドレスまたはパスワードを確認",
  );
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
});
