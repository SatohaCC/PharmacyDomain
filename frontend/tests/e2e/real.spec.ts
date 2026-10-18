import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("実APIとPostgreSQLで新規契約から初回ログインまで完了する", async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.REAL_E2E_TOKENS,
    "専用DBと実APIを用意した実行だけが対象",
  );
  const tokens = JSON.parse(
    readFileSync(process.env.REAL_E2E_TOKENS!, "utf8"),
  ) as { vendor: string };
  const loginId = `test-admin-${Date.now()}`;
  await page.goto("/login");
  await page.getByLabel("Bearerトークン").fill(tokens.vendor);
  await page.getByRole("button", { name: "接続する" }).click();
  await page.getByRole("link", { name: "法人を登録", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "新規契約登録", exact: true }),
  ).toBeVisible();
  await page.getByLabel("法人名").fill(`ブラウザーテスト法人${Date.now()}`);
  await page.getByLabel("代表者の姓").fill("テスト");
  await page.getByLabel("代表者の名").fill("太郎");
  await page.getByLabel(/^管理者の姓(?:必須| 必須)?$/).fill("テスト");
  await page.getByLabel(/^管理者の名(?:必須| 必須)?$/).fill("花子");
  await page.getByLabel("管理者の姓（カナ）").fill("テスト");
  await page.getByLabel("管理者の名（カナ）").fill("ハナコ");
  await page.getByLabel("ログインID").fill(loginId);
  await page.getByLabel("初期パスワード").fill("test-initial-password-12345");
  await page.getByRole("button", { name: "登録する" }).click();
  await expect(
    page.getByRole("heading", { name: /ブラウザーテスト法人/ }),
  ).toBeVisible();
  const corporateUrl = new URL(page.url()).pathname;
  const context = await browser.newContext();
  const administrator = await context.newPage();
  try {
    await administrator.goto("/login");
    await administrator.getByLabel("ログインID").fill(loginId);
    await administrator
      .getByLabel(/^パスワード(?:必須| 必須)?$/)
      .fill("test-initial-password-12345");
    await administrator
      .getByRole("button", { name: "ログイン", exact: true })
      .click();
    await expect(
      administrator.getByRole("heading", { name: "初回パスワード変更" }),
    ).toBeVisible();
    await administrator
      .getByLabel(/^新しいパスワード(?:必須| 必須)?$/)
      .fill("test-changed-password-67890");
    await administrator
      .getByLabel("新しいパスワード（確認）")
      .fill("test-changed-password-67890");
    await administrator
      .getByRole("button", { name: "パスワードを変更して利用開始" })
      .click();
    await expect(
      administrator.getByRole("heading", { name: /ブラウザーテスト法人/ }),
    ).toBeVisible();
    expect(new URL(administrator.url()).pathname).toBe(corporateUrl);
    await administrator.screenshot({
      path: "test-results/real-local-authentication-completed.png",
      fullPage: true,
    });
  } finally {
    await context.close();
  }
});
