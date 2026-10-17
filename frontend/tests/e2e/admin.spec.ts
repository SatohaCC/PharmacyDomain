import { test, expect, type Page } from "@playwright/test";
const corp = {
  id: "corp-1",
  name: "テスト薬局グループ",
  representative_name: "テスト 太郎",
  is_active: true,
};
const actor = {
  person_id: "admin-person",
  account_id: "admin-account",
  membership_id: null,
  corporate_id: null,
  roles: ["vendor_system_admin"],
  staff_id: null,
  store_ids: [],
};
async function mock(page: Page, roles = actor.roles) {
  const stores: {
    id: string;
    corporate_id: string;
    name: string;
    name_kana: string;
    code: null;
  }[] = [];
  let people = 0;
  let invites = 0;
  await page.route(
    /\/api\/(?:me|corporates|user-invitations)(?:[/?]|$)/,
    async (route) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.slice(4);
      const method = req.method();
      let value: unknown;
      if (path === "/me")
        value = {
          ...actor,
          roles,
          corporate_id: roles.includes("corporate_admin") ? "corp-1" : null,
        };
      else if (path === "/corporates" && method === "POST")
        value = { id: corp.id };
      else if (path === "/corporates")
        value = { items: [corp], next_cursor: null };
      else if (path === "/corporates/corp-1") value = corp;
      else if (path.endsWith("/stores") && method === "POST") {
        const body = req.postDataJSON();
        stores.push({
          id: "store-1",
          corporate_id: "corp-1",
          name: body.name,
          name_kana: body.name_kana,
          code: null,
        });
        value = { id: "store-1" };
      } else if (path.endsWith("/stores")) value = stores;
      else if (path.endsWith("/staffs")) value = [];
      else if (path.endsWith("/people")) {
        people++;
        value = { id: "person-1" };
      } else if (path.endsWith("/user-invitations")) {
        invites++;
        if (invites === 1) {
          await route.fulfill({
            status: 409,
            json: {
              code: "CONFLICT",
              message: "招待が競合しました。",
              errors: [],
            },
          });
          return;
        }
        value = { id: "invite-1", secret: "test-secret" };
      } else if (path === "/user-invitations/acceptance")
        value = { id: "account-1" };
      else if (path.endsWith("/users"))
        value = { items: [], next_cursor: null };
      else value = {};
      await route.fulfill({ json: value });
    },
  );
  return { people: () => people, invites: () => invites };
}
async function connect(page: Page, target = "/admin") {
  await page.goto("/login?returnTo=" + encodeURIComponent(target));
  await page.getByLabel("Bearerトークン").fill("test-token");
  await page.getByRole("button", { name: "接続する" }).click();
}
test("法人と店舗を登録できる", async ({ page }) => {
  await mock(page);
  await connect(page);
  await page.getByRole("link", { name: "法人を登録", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "法人登録", exact: true }),
  ).toBeVisible();
  await page.getByLabel("法人名").fill(corp.name);
  await page.getByLabel("代表者の姓").fill("テスト");
  await page.getByLabel("代表者の名").fill("太郎");
  await page.getByRole("button", { name: "登録する" }).click();
  await expect(page.getByRole("heading", { name: corp.name })).toBeVisible();
  await page.getByRole("link", { name: /店舗を登録/ }).click();
  for (const [label, value] of [
    ["店舗名", "テスト薬局本店"],
    ["店舗名カナ", "テストヤッキョクホンテン"],
    ["郵便番号", "1000001"],
    ["住所", "東京都千代田区"],
    ["電話番号", "0312345678"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByRole("button", { name: "登録する" }).click();
  await expect(
    page.getByRole("cell", { name: "テスト薬局本店", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/admin-stores.png",
    fullPage: true,
  });
});
test("招待失敗から本人の再登録なしに再試行できる", async ({ page }) => {
  const state = await mock(page);
  await connect(page, "/admin/corporates/corp-1/users/new");
  for (const [label, value] of [
    ["姓", "テスト"],
    ["名", "花子"],
    ["姓カナ", "テスト"],
    ["名カナ", "ハナコ"],
  ])
    await page
      .getByLabel(label, { exact: false })
      .filter({ visible: true })
      .first()
      .fill(value);
  await page.getByLabel("宛先メールアドレス").fill("hanako@example.test");
  await page.getByLabel("招待期限").fill("2030-01-01T12:00");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(page.getByRole("alert")).toContainText("招待が競合");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  expect(state.people()).toBe(1);
  expect(state.invites()).toBe(2);
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toContain("test-secret");
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("再表示");
    await dialog.dismiss();
  });
  await page.getByRole("link", { name: "ユーザー一覧へ" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("link", { name: "ユーザー一覧へ" }).click();
  await expect(
    page.getByRole("heading", { name: "ユーザー一覧" }),
  ).toBeVisible();
  await expect(page.getByLabel("招待URL", { exact: false })).toHaveCount(0);
});
test("法人管理者には法人登録を表示しない", async ({ page }) => {
  await mock(page, ["corporate_admin"]);
  await connect(page);
  await expect(page.getByRole("heading", { name: corp.name })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "法人を登録", exact: true }),
  ).toHaveCount(0);
});
test("未登録の人も招待画面へ到達でき秘密をURLから除去する", async ({
  page,
}) => {
  await page.goto("/invitations/accept#secret=invitation-test");
  await expect(
    page.getByRole("heading", { name: "法人への招待" }),
  ).toBeVisible();
  await expect(page.getByLabel("招待の秘密")).toHaveValue("invitation-test");
  expect(new URL(page.url()).hash).toBe("");
  await page.reload();
  await expect(page.getByLabel("招待の秘密")).toHaveValue("");
});
test("招待画面から開発ログイン後に秘密を保存せず招待画面へ戻る", async ({ page }) => {
  await mock(page);
  await page.goto("/invitations/accept#secret=invitation-test");
  await expect(page.getByLabel("招待の秘密")).toHaveValue("invitation-test");
  await page.getByRole("link", { name: "開発用トークンで接続" }).click();
  await expect(page).toHaveURL(/\/login\?returnTo=%2Finvitations%2Faccept$/);
  await page.getByLabel("Bearerトークン").fill("test-token");
  await page.getByRole("button", { name: "接続する" }).click();
  await expect(page).toHaveURL(/\/invitations\/accept$/);
  await expect(page.getByRole("heading", { name: "法人への招待" })).toBeVisible();
  await expect(page.getByLabel("招待の秘密")).toHaveValue("");
});
test("店舗ロールは受諾完了後に管理画面へ飛ばされない", async ({ page }) => {
  await mock(page, ["store_viewer"]);
  await connect(page, "/invitations/accept");
  await page.getByLabel("招待の秘密").fill("test-secret");
  await page.getByRole("button", { name: "招待を受諾する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を受諾しました" }),
  ).toBeVisible();
  await expect(
    page.getByText("業務画面は準備中", { exact: false }),
  ).toBeVisible();
});
test("店舗ロールは管理画面に入れない", async ({ page }) => {
  await mock(page, ["store_viewer"]);
  await connect(page);
  await expect(page.getByRole("alert")).toContainText("権限");
});

test("未認証の管理画面直リンクはログインへ戻る", async ({ page }) => {
  await page.goto("/admin/corporates/new");
  await expect(
    page.getByRole("heading", { name: "管理画面にログイン" }),
  ).toBeVisible();
});
for (const [status, message] of [
  [422, "法人名を確認してください。"],
  [409, "法人が競合しています。"],
  [500, "サーバー処理に失敗しました。"],
] as const) {
  test(`法人登録の${status}を成功として扱わない`, async ({ page }) => {
    await mock(page);
    await page.route("**/api/corporates", async (route) => {
      if (route.request().method() === "POST")
        await route.fulfill({
          status,
          json: { code: "ERROR", message, errors: [] },
        });
      else await route.fallback();
    });
    await connect(page, "/admin/corporates/new");
    await page.getByLabel("法人名").fill("失敗検証法人");
    await page.getByLabel("代表者の姓").fill("テスト");
    await page.getByLabel("代表者の名").fill("太郎");
    await page.getByRole("button", { name: "登録する" }).click();
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByLabel("法人名")).toHaveValue("失敗検証法人");
    await expect(
      page.getByRole("heading", { name: "法人登録", exact: true }),
    ).toBeVisible();
    if (status === 500)
      await expect(
        page.getByRole("button", { name: "処理結果を確認してください" }),
      ).toBeDisabled();
  });
}
test("招待が利用できない場合は受諾完了を表示しない", async ({ page }) => {
  await mock(page);
  await page.route("**/api/user-invitations/acceptance", (route) =>
    route.fulfill({
      status: 409,
      json: {
        code: "IDENTITY_CONFLICT",
        message: "この招待は利用できません。",
        errors: [],
      },
    }),
  );
  await connect(page, "/invitations/accept");
  await page.getByLabel("招待の秘密").fill("expired");
  await page.getByRole("button", { name: "招待を受諾する" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "この招待は利用できません。",
  );
  await expect(
    page.getByRole("heading", { name: "招待を受諾しました" }),
  ).toHaveCount(0);
});
test("受諾POSTの通信結果不明時は二重受諾を送らない", async ({ page }) => {
  await mock(page);
  let calls = 0;
  await page.route("**/api/user-invitations/acceptance", async (route) => {
    calls++;
    await route.abort();
  });
  await connect(page, "/invitations/accept");
  await page.getByLabel("招待の秘密").fill("unknown");
  await page.getByRole("button", { name: "招待を受諾する" }).click();
  await expect(page.getByRole("alert")).toContainText("通信が途切れ");
  await expect(
    page.getByRole("button", { name: "処理結果を確認してください" }),
  ).toBeDisabled();
  expect(calls).toBe(1);
});
test("別法人への直リンクを法人管理者は表示できない", async ({ page }) => {
  await mock(page, ["corporate_admin"]);
  await connect(page, "/admin/corporates/corp-other");
  await expect(page.getByRole("alert")).toContainText("見つかりません");
  await expect(page.getByRole("heading", { name: corp.name })).toHaveCount(0);
});
test("狭い画面でも管理操作が表示される", async ({ page }) => {
  await mock(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await connect(page);
  await expect(
    page.getByRole("link", { name: "法人を登録", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/admin-mobile.png",
    fullPage: true,
  });
});
test("店舗ロールの招待はスタッフ紐付け後に発行する", async ({ page }) => {
  const state = await mock(page);
  await page.route("**/api/corporates/corp-1/stores", (r) =>
    r.fulfill({
      json: [
        {
          id: "store-1",
          corporate_id: "corp-1",
          name: "テスト店舗",
          name_kana: "テスト",
          code: null,
        },
      ],
    }),
  );
  await page.route("**/api/corporates/corp-1/staffs", (r) =>
    r.fulfill({
      json: [
        {
          id: "staff-1",
          last_name: "テスト",
          first_name: "太郎",
          last_name_kana: "テスト",
          first_name_kana: "タロウ",
          is_active: true,
          is_pharmacist: false,
        },
      ],
    }),
  );
  let linkCalls = 0;
  await page.route(
    "**/api/corporates/corp-1/staffs/staff-1/person-link",
    (r) => {
      linkCalls++;
      expect(r.request().postDataJSON().person_id).toBe("person-1");
      return r.fulfill({ json: { id: "staff-1" } });
    },
  );
  await connect(page, "/admin/corporates/corp-1/users/new");
  for (const [label, value] of [
    ["姓", "テスト"],
    ["名", "太郎"],
    ["姓カナ", "テスト"],
    ["名カナ", "タロウ"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByRole("button", { name: / ロール$/ }).click();
  await page.getByRole("option", { name: "店舗閲覧者", exact: true }).click();
  await page.getByText("テスト店舗", { exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "テスト店舗", exact: true }),
  ).toBeChecked();
  await page.getByRole("button", { name: / スタッフ(?:必須| 必須)?$/ }).click();
  await page.getByRole("option", { name: "テスト 太郎", exact: true }).click();
  await page.getByLabel("宛先メールアドレス").fill("staff@example.test");
  await page.getByLabel("招待期限").fill("2030-01-01T12:00");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(page.getByRole("alert")).toContainText("競合");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  expect(linkCalls).toBe(1);
  expect(state.people()).toBe(1);
});

test("法人検索を変更すると前ページのカーソルを破棄する", async ({ page }) => {
  await mock(page);
  const queries: string[] = [];
  await page.route(/\/api\/corporates(?:\?|$)/, async (route) => {
    const url = new URL(route.request().url());
    queries.push(url.search);
    const cursor = url.searchParams.get("cursor");
    await route.fulfill({
      json: { items: [corp], next_cursor: cursor ? null : "next-page" },
    });
  });
  await connect(page);
  await page.getByRole("link", { name: "次のページ" }).click();
  await expect(page.getByRole("link", { name: "次のページ" })).toHaveCount(0);
  await page.getByLabel("法人名で検索").fill("テスト");
  await page.getByRole("button", { name: "検索する" }).click();
  await expect(page.getByRole("link", { name: "次のページ" })).toBeVisible();
  expect(queries.some((q) => q.includes("cursor=next-page"))).toBeTruthy();
  const last = new URLSearchParams(queries.at(-1));
  expect(last.get("name")).toBe("テスト");
  expect(last.has("cursor")).toBeFalsy();
});
test("法人を切り替えた後に前法人の遅い店舗応答を表示しない", async ({
  page,
}) => {
  await mock(page);
  await page.route("**/api/corporates", (route) =>
    route.fulfill({
      json: {
        items: [corp, { ...corp, id: "corp-2", name: "第二法人" }],
        next_cursor: null,
      },
    }),
  );
  await page.route("**/api/corporates/corp-2", (route) =>
    route.fulfill({ json: { ...corp, id: "corp-2", name: "第二法人" } }),
  );
  await page.route("**/api/corporates/corp-2/stores", (route) =>
    route.fulfill({
      json: [
        { id: "second", name: "第二店舗", name_kana: "ダイニ", code: null },
      ],
    }),
  );
  await page.route("**/api/corporates/corp-1/stores", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await route
      .fulfill({
        json: [
          { id: "first", name: "前法人の店舗", name_kana: "マエ", code: null },
        ],
      })
      .catch(() => {});
  });
  await connect(page);
  await page.getByRole("link", { name: "管理する" }).first().click();
  await expect(page.getByRole("heading", { name: corp.name })).toBeVisible();
  await page.getByRole("link", { name: "店舗", exact: true }).hover();
  await page.getByRole("link", { name: "法人管理", exact: true }).click();
  await page.getByRole("link", { name: "管理する" }).nth(1).click();
  await expect(page.getByRole("heading", { name: "第二法人" })).toBeVisible();
  await page.getByRole("link", { name: "店舗", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "第二店舗", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("cell", { name: "前法人の店舗" })).toHaveCount(0);
});

test("既存本人IDの招待では本人登録を繰り返さない", async ({ page }) => {
  const state = await mock(page);
  await connect(page, "/admin/corporates/corp-1/users/new");
  await page.getByRole("button", { name: / 本人の指定$/ }).click();
  await page
    .getByRole("option", { name: "登録済みの本人IDを指定", exact: true })
    .click();
  await page.getByRole("textbox", { name: /^本人ID/ }).fill("existing-person");
  await page.getByLabel("宛先メールアドレス").fill("existing@example.test");
  await page.getByLabel("招待期限").fill("2030-01-01T12:00");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(page.getByRole("alert")).toContainText("競合");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  expect(state.people()).toBe(0);
});
test("店舗ユーザーのスタッフを新規登録して招待できる", async ({ page }) => {
  await mock(page);
  await page.route("**/api/corporates/corp-1/stores", (r) =>
    r.fulfill({
      json: [
        {
          id: "store-1",
          name: "テスト店舗",
          name_kana: "テスト",
          code: null,
        },
      ],
    }),
  );
  let created = 0;
  await page.route("**/api/corporates/corp-1/staffs", async (r) => {
    if (r.request().method() === "POST") {
      created++;
      expect(r.request().postDataJSON().initial_home_store_id).toBe("store-1");
      await r.fulfill({ json: { id: "staff-new" } });
    } else await r.fulfill({ json: [] });
  });
  await page.route(
    "**/api/corporates/corp-1/staffs/staff-new/person-link",
    (r) => r.fulfill({ json: { id: "staff-new" } }),
  );
  await connect(page, "/admin/corporates/corp-1/users/new");
  for (const [label, value] of [
    ["姓", "テスト"],
    ["名", "太郎"],
    ["姓カナ", "テスト"],
    ["名カナ", "タロウ"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByRole("button", { name: / ロール$/ }).click();
  await page.getByRole("option", { name: "店舗操作者", exact: true }).click();
  await page.getByText("テスト店舗", { exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "テスト店舗", exact: true }),
  ).toBeChecked();
  await page.getByRole("button", { name: / スタッフの指定$/ }).click();
  await page
    .getByRole("option", { name: "スタッフを新規登録", exact: true })
    .click();
  await page.getByRole("button", { name: / 主所属店舗(?:必須| 必須)?$/ }).click();
  await page.getByRole("option", { name: "テスト店舗", exact: true }).click();
  await page.getByLabel("所属開始日").fill("2026-10-01");
  await page.getByLabel("宛先メールアドレス").fill("newstaff@example.test");
  await page.getByLabel("招待期限").fill("2030-01-01T12:00");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(page.getByRole("alert")).toContainText("競合");
  await page.getByRole("button", { name: "招待を発行する" }).click();
  await expect(
    page.getByRole("heading", { name: "招待を発行しました" }),
  ).toBeVisible();
  expect(created).toBe(1);
});
