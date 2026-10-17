import { test, expect } from "@playwright/test";
const stories = [
  ["法人登録", "画面-法人登録--通常"],
  ["法人登録の失敗", "画面-法人登録--登録失敗"],
  ["店舗登録", "画面-店舗登録--通常"],
  ["ユーザー登録", "画面-ユーザー登録と招待--通常"],
  ["招待受諾", "画面-招待受諾--通常"],
  ["トークン", "デザイン-トークン--一覧"],
] as const;
for (const [name, id] of stories) {
  for (const width of [1280, 390]) {
    test(`${name}を${width}pxで表示する`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(
        `/iframe.html?id=${encodeURIComponent(id)}&viewMode=story`,
      );
      await expect(page.locator("#storybook-root")).not.toBeEmpty();
      await page.evaluate(() => document.fonts.ready);
      await expect(page.getByRole("heading").first()).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await expect(page).toHaveScreenshot(`${id}-${width}.png`, {
        fullPage: true,
        animations: "disabled",
      });
    });
  }
}
