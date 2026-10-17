import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
test("実APIとPostgreSQLで法人・店舗・ユーザー登録から受諾まで完了する", async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.REAL_E2E_TOKENS,
    "専用DBとJWT検証サーバーを用意した実行だけが対象",
  );
  const tokens = JSON.parse(
    readFileSync(process.env.REAL_E2E_TOKENS!, "utf8"),
  ) as { vendor: string; invitee: string };
  await page.goto("/login");
  await page.getByLabel("Bearerトークン").fill(tokens.vendor);
  await page.getByRole("button", { name: "接続する" }).click();
  await page.getByRole("link", { name: "法人を登録", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "法人登録", exact: true }),
  ).toBeVisible();
  await page.getByLabel("法人名").fill("ブラウザーテスト法人");
  await page.getByLabel("代表者の姓").fill("テスト");
  await page.getByLabel("代表者の名").fill("太郎");
  await page.getByRole("button", { name: "登録する" }).click();
  await expect(
    page.getByRole("heading", { name: "ブラウザーテスト法人" }),
  ).toBeVisible();
  const corporateUrl = new URL(page.url()).pathname;
  await page.getByRole("link", { name: /店舗を登録/ }).click();
  for (const [label, value] of [
    ["店舗名", "テスト薬局"],
    ["店舗名カナ", "テストヤッキョク"],
    ["郵便番号", "1000001"],
    ["住所", "東京都千代田区千代田1"],
    ["電話番号", "0312345678"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByRole("button", { name: "登録する" }).click();
  await expect(
    page.getByRole("cell", { name: "テスト薬局", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "ユーザー", exact: true }).click();
  await page.getByRole("link", { name: "ユーザーを招待", exact: true }).click();
  for (const [label, value] of [
    ["姓", "テスト"],
    ["名", "花子"],
    ["姓カナ", "テスト"],
    ["名カナ", "ハナコ"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByLabel("宛先メールアドレス").fill("browser@example.test");
  await page.getByLabel("招待期限").fill("2030-01-01T12:00");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  const invitation = await page
    .getByLabel("招待URL", { exact: false })
    .inputValue();
  const secret = new URLSearchParams(new URL(invitation).hash.slice(1)).get(
    "secret",
  )!;
  const context = await browser.newContext();
  const invitee = await context.newPage();
  try {
    await invitee.goto("/login?returnTo=/invitations/accept");
    await invitee.getByLabel("Bearerトークン").fill(tokens.invitee);
    await invitee.getByRole("button", { name: "接続する" }).click();
    await expect(
      invitee.getByRole("heading", { name: "法人への招待" }),
    ).toBeVisible();
    await invitee.getByLabel("招待の秘密").fill(secret);
    await invitee.getByRole("button", { name: "招待を受諾する" }).click();
    await expect(
      invitee.getByRole("heading", { name: "招待を受諾しました" }),
    ).toBeVisible();
    await invitee.getByRole("link", { name: "法人管理へ" }).click();
    await expect(
      invitee.getByRole("heading", { name: "ブラウザーテスト法人" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "受諾状態を確認" }).click();
    await expect(page.getByRole("status")).toContainText("受諾済み");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("link", { name: "ユーザー一覧へ" }).click();
    await expect(
      page.getByRole("cell", { name: "法人管理者", exact: true }),
    ).toBeVisible();
    expect(corporateUrl).toContain("/admin/corporates/");
  } finally {
    await context.close();
  }
});
