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
  let registrations = 0;
  await page.route(
    /\/api\/(?:me|corporates|contracts)(?:[/?]|$)/,
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
      else if (
        (path === "/corporates" || path === "/contracts") &&
        method === "POST"
      )
        value = { id: corp.id };
      else if (path === "/me/stores") value = [];
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
      else if (path.endsWith("/staffs") && method === "POST") {
        registrations++;
        value = {
          staff_id: "staff-1",
          person_id: "person-1",
          account_id: "account-1",
          membership_id: "membership-1",
          login_id: req.postDataJSON().account.login_id,
        };
      } else if (path.endsWith("/staffs")) value = [];
      else if (path.endsWith("/users"))
        value = { items: [], next_cursor: null };
      else value = {};
      await route.fulfill({ json: value });
    },
  );
  return { registrations: () => registrations };
}
async function connect(page: Page, target = "/admin") {
  await page.goto("/login?returnTo=" + encodeURIComponent(target));
  await page.getByLabel("Bearerトークン").fill("test-token");
  await page.getByRole("button", { name: "接続する" }).click();
}

test("所属店舗ごとに週時間数を保存し再読込後も独立して表示する", async ({
  page,
}) => {
  await page.clock.install({ time: new Date("2026-11-02T03:00:00Z") });
  await mock(page);
  const stores = [
    { id: "store-a", name: "A薬局" },
    { id: "store-b", name: "B薬局" },
  ];
  await page.route("**/api/corporates/corp-1/stores", (route) =>
    route.fulfill({ json: stores }),
  );
  await page.route("**/api/corporates/corp-1/users/member-1", (route) =>
    route.fulfill({
      json: {
        id: "member-1",
        account_id: "account-1",
        person_id: "person-1",
        corporate_id: "corp-1",
        role: "member",
        status: "active",
        account_status: "active",
        staff_id: "staff-1",
        store_ids: ["store-a", "store-b"],
        store_roles: [
          { store_id: "store-a", role: "store_operator" },
          { store_id: "store-b", role: "store_viewer" },
        ],
      },
    }),
  );
  await page.route("**/api/corporates/corp-1/staffs/staff-1", (route) =>
    route.fulfill({
      json: {
        id: "staff-1",
        corporate_id: "corp-1",
        last_name: "テスト",
        first_name: "太郎",
        last_name_kana: "テスト",
        first_name_kana: "タロウ",
        is_active: true,
        employment_type: "regular",
      },
    }),
  );
  const saved: {
    store: string;
    weekly_hours: string | null;
    effective_from: string;
    duty: string;
  }[] = [];
  await page.route(
    "**/api/corporates/corp-1/staffs/staff-1/**",
    async (route) => {
      const rows = ["store-a", "store-b"].map((store) => {
        const history = saved
          .filter((item) => item.store === store)
          .map((item) => ({
            ...item,
            recorded_at: "2026-11-03T03:00:00Z",
            recorded_by: "vendor",
          }));
        return {
          store_id: store,
          starts_on: "2026-01-01",
          ends_on: null,
          is_primary: store === "store-a",
          current: history.at(-1) || null,
          history,
        };
      });
      await route.fulfill({ json: rows });
    },
  );
  let saveCalls = 0;
  await page.route("**/api/corporates/corp-1/users/member-1", (route) => {
    if (route.request().method() !== "PATCH")
      return route.fulfill({
        json: {
          id: "member-1",
          account_id: "account-1",
          person_id: "person-1",
          corporate_id: "corp-1",
          role: "member",
          status: "active",
          account_status: "active",
          staff_id: "staff-1",
          store_ids: ["store-a", "store-b"],
          store_roles: [
            { store_id: "store-a", role: "store_operator" },
            { store_id: "store-b", role: "store_viewer" },
          ],
        },
      });
    saveCalls++;
    const body = route.request().postDataJSON();
    expect(body.store_roles).toEqual([
      { store_id: "store-a", role: "store_operator" },
      { store_id: "store-b", role: "store_viewer" },
    ]);
    for (const item of body.store_work_conditions)
      saved.push({ store: item.store_id, ...item });
    return route.fulfill({ json: { id: "member-1" } });
  });
  await connect(page, "/admin/corporates/corp-1/users/member-1");
  await page
    .getByRole("button", { name: "所属・権限・勤務時間を変更" })
    .click();
  await expect(page.getByRole("checkbox", { name: "A薬局" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "B薬局" })).toBeChecked();
  await page.getByLabel("A薬局の週勤務時間（時間）").fill("32");
  await page.getByLabel("B薬局の週勤務時間（時間）").fill("8");
  await page.getByLabel("A薬局の勤務条件の適用開始日").fill("2026-11-01");
  await page.getByLabel("B薬局の勤務条件の適用開始日").fill("2026-11-02");
  await page
    .getByRole("button", { name: "所属・権限・勤務時間を保存する" })
    .click();
  await expect(
    page.getByText("所属店舗・権限・勤務時間を更新しました。"),
  ).toBeVisible();
  expect(saveCalls).toBe(1);
  expect(saved.map((item) => [item.store, item.weekly_hours])).toEqual([
    ["store-a", "32"],
    ["store-b", "8"],
  ]);
  await page.reload();
  await expect(
    page.getByRole("cell", { name: "32時間", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "8時間", exact: true }),
  ).toBeVisible();
});
test("法人と店舗を登録できる", async ({ page }) => {
  await mock(page);
  await connect(page);
  await page.getByRole("link", { name: "法人を登録", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "新規契約登録", exact: true }),
  ).toBeVisible();
  await page.getByLabel("法人名").fill(corp.name);
  await page.getByLabel("代表者の姓").fill("テスト");
  await page.getByLabel("代表者の名").fill("太郎");
  await page.getByLabel(/^管理者の姓(?:必須| 必須)?$/).fill("テスト");
  await page.getByLabel(/^管理者の名(?:必須| 必須)?$/).fill("花子");
  await page.getByLabel("管理者の姓（カナ）").fill("テスト");
  await page.getByLabel("管理者の名（カナ）").fill("ハナコ");
  await page.getByLabel("ログインID").fill("test-admin");
  await page.getByLabel("初期パスワード").fill("test-initial-password-12345");
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
test("法人管理者には法人登録を表示しない", async ({ page }) => {
  await mock(page, ["corporate_admin"]);
  await connect(page);
  await expect(page.getByRole("heading", { name: corp.name })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "法人を登録", exact: true }),
  ).toHaveCount(0);
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
    await page.route("**/api/contracts", async (route) => {
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
    await page.getByLabel(/^管理者の姓(?:必須| 必須)?$/).fill("テスト");
    await page.getByLabel(/^管理者の名(?:必須| 必須)?$/).fill("花子");
    await page.getByLabel("管理者の姓（カナ）").fill("テスト");
    await page.getByLabel("管理者の名（カナ）").fill("ハナコ");
    await page.getByLabel("ログインID").fill("test-admin");
    await page.getByLabel("初期パスワード").fill("test-initial-password-12345");
    await page.getByRole("button", { name: "登録する" }).click();
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByLabel("法人名")).toHaveValue("失敗検証法人");
    await expect(
      page.getByRole("heading", { name: "新規契約登録", exact: true }),
    ).toBeVisible();
    if (status === 500)
      await expect(
        page.getByRole("button", { name: "処理結果を確認してください" }),
      ).toBeDisabled();
  });
}
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

for (const role of ["法人管理者", "一般ユーザー"]) {
  test(`ユーザー一括登録_${role}_本人と主所属とログインIDを一要求で送る`, async ({
    page,
  }) => {
    await mock(page);
    await page.route("**/api/corporates/corp-1/stores", (r) =>
      r.fulfill({
        json: [
          { id: "store-1", name: "テスト店舗" },
          { id: "store-2", name: "兼務店舗" },
        ],
      }),
    );
    let calls = 0;
    await page.route("**/api/corporates/corp-1/staffs", async (r) => {
      expect(r.request().method()).toBe("POST");
      calls++;
      expect(r.request().postDataJSON()).toMatchObject({
        last_name: "テスト",
        first_name: "太郎",
        initial_home_store_id: "store-1",
        initial_start_date: "2026-10-01",
        initial_store_work_conditions: [
          {
            store_id: "store-1",
            starts_on: "2026-10-01",
            weekly_hours: "32",
            duty: "other",
          },
          {
            store_id: "store-2",
            starts_on: "2026-11-01",
            weekly_hours: "8",
            duty: "other",
          },
        ],
        account: {
          login_id: "test-user",
          email: null,
          password: "test-initial-password-12345",
          role: role === "法人管理者" ? "corporate_admin" : "member",
          store_roles: [
            { store_id: "store-1", role: "store_operator" },
            { store_id: "store-2", role: "store_viewer" },
          ],
        },
      });
      if (calls === 1)
        return r.fulfill({
          status: 409,
          json: {
            code: "CONFLICT",
            message: "登録が競合しました。",
            errors: [],
          },
        });
      return r.fulfill({
        status: 201,
        json: {
          staff_id: "staff-1",
          person_id: "person-1",
          account_id: "account-1",
          membership_id: "membership-1",
          login_id: "test-user",
        },
      });
    });
    await connect(page, "/admin/corporates/corp-1/users/new");
    await expect(page.getByText("登録済みの本人IDを指定")).toHaveCount(0);
    await expect(page.getByText("既存スタッフを選択")).toHaveCount(0);
    for (const [label, value] of [
      ["姓", "テスト"],
      ["名", "太郎"],
      ["姓カナ", "テスト"],
      ["名カナ", "タロウ"],
    ])
      await page.getByLabel(label, { exact: false }).first().fill(value);
    if (role !== "法人管理者") {
      await page.getByRole("button", { name: /ロール$/ }).click();
      await page.getByRole("option", { name: role, exact: true }).click();
    }
    await page
      .getByText("テスト店舗", { exact: true })
      .filter({ visible: true })
      .click();
    await page
      .getByText("兼務店舗", { exact: true })
      .filter({ visible: true })
      .click();
    await page.getByRole("button", { name: /兼務店舗の操作権限/ }).click();
    await page.getByRole("option", { name: "閲覧のみ", exact: true }).click();
    await page.getByLabel("テスト店舗の週勤務時間（時間）").fill("32");
    await page.getByLabel("兼務店舗の週勤務時間（時間）").fill("8");
    await page.getByRole("button", { name: /主所属店舗/ }).click();
    await page.getByRole("option", { name: "テスト店舗", exact: true }).click();
    await page.getByLabel("テスト店舗の所属開始日").fill("2026-10-01");
    await page.getByLabel("兼務店舗の所属開始日").fill("2026-11-01");
    await page.getByLabel("ログインID").fill("test-user");
    await page.getByLabel("初期パスワード").fill("test-initial-password-12345");
    await page.getByRole("button", { name: "ユーザーを登録する" }).click();
    await expect(page.getByRole("alert")).toContainText("登録が競合");
    await page.getByRole("button", { name: "ユーザーを登録する" }).click();
    await expect(
      page.getByRole("heading", { name: "ユーザー登録が完了しました" }),
    ).toBeVisible();
    await expect(page.getByText("test-user")).toBeVisible();
    expect(calls).toBe(2);
    expect(
      await page.evaluate(() =>
        JSON.stringify({ ...localStorage, ...sessionStorage }),
      ),
    ).not.toContain("test-initial-password-12345");
  });
}

test("ユーザー一括登録_通信結果不明_再送を止める", async ({ page }) => {
  await mock(page);
  let calls = 0;
  await page.route("**/api/corporates/corp-1/staffs", async (r) => {
    calls++;
    await r.abort();
  });
  await connect(page, "/admin/corporates/corp-1/users/new");
  for (const [label, value] of [
    ["姓", "テスト"],
    ["名", "太郎"],
    ["姓カナ", "テスト"],
    ["名カナ", "タロウ"],
    ["ログインID", "test-user"],
    ["初期パスワード", "test-initial-password-12345"],
  ])
    await page.getByLabel(label, { exact: false }).first().fill(value);
  await page.getByRole("button", { name: "ユーザーを登録する" }).click();
  await expect(
    page.getByRole("button", { name: "処理結果を確認してください" }),
  ).toBeDisabled();
  expect(calls).toBe(1);
});

for (const vendor of [false, true]) {
  test(`ログインID認証_${vendor ? "運営者" : "法人ユーザー"}_対応するAPIでログインする`, async ({
    page,
  }) => {
    await mock(page);
    let calls = 0;
    await page.route(
      vendor ? "**/api/auth/vendor/login" : "**/api/auth/login",
      (r) => {
        calls++;
        expect(r.request().postDataJSON()).toEqual({
          ...(vendor ? {} : { corporate_code: "012345" }),
          login_id: "test-admin",
          password: "test-password-12345",
        });
        return r.fulfill({
          json: { access_token: "test-token", password_change_required: false },
        });
      },
    );
    await page.goto("/login");
    if (vendor) {
      await page.getByRole("button", { name: /ログイン種別/ }).click();
      await page.getByRole("option", { name: "運営者", exact: true }).click();
      await expect(page.getByLabel("6桁の法人コード")).toHaveCount(0);
    } else await page.getByLabel("6桁の法人コード").fill("012345");
    await page.getByLabel("ログインID").fill("test-admin");
    await page.getByLabel(/^パスワード/).fill("test-password-12345");
    await page.getByRole("button", { name: "ログイン", exact: true }).click();
    await expect(
      page.getByRole("link", { name: "法人を登録", exact: true }),
    ).toBeVisible();
    expect(calls).toBe(1);
  });
}
