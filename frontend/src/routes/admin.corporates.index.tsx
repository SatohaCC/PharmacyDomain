import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { api, result } from "../shared/api/client";
import { Empty, Field, Form, text } from "../shared/ui/common";
export const Route = createFileRoute("/admin/corporates/")({
  validateSearch: (
    s: Record<string, unknown>,
  ): { name?: string; status?: string; cursor?: string } => ({
    name: typeof s.name === "string" ? s.name : "",
    status: typeof s.status === "string" ? s.status : "",
    cursor: typeof s.cursor === "string" ? s.cursor : undefined,
  }),
  loaderDeps: ({ search }) => search,
  beforeLoad: ({ context }) => {
    if (!context.actor.roles.includes("vendor_system_admin"))
      throw new Error("法人一覧を表示する権限がありません。");
  },
  loader: ({ deps, abortController }) =>
    result(
      api.GET("/corporates", {
        params: {
          query: {
            name: deps.name || undefined,
            status: deps.status || undefined,
            cursor: deps.cursor,
          },
        },
        signal: abortController.signal,
      }),
    ),
  component: Corporates,
});
function Corporates() {
  const data = Route.useLoaderData();
  const search = Route.useSearch();
  const navigate = useNavigate();
  return (
    <>
      <div className="title">
        <div>
          <h1>法人管理</h1>
          <p>登録済みの法人を確認・追加します。</p>
        </div>
        <Link className="button" to="/admin/corporates/new">
          法人を登録
        </Link>
      </div>
      <section>
        <Form
          label="検索する"
          onSubmit={async (d) => {
            await navigate({
              to: "/admin/corporates",
              search: {
                name: text(d, "name"),
                status: text(d, "status"),
                cursor: undefined,
              },
            });
          }}
        >
          <div className="row">
            <Field
              name="name"
              label="法人名で検索"
              defaultValue={search.name}
            />
            <label className="field">
              状態
              <select name="status" defaultValue={search.status}>
                <option value="">すべて</option>
                <option value="active">有効</option>
                <option value="inactive">停止</option>
              </select>
            </label>
          </div>
        </Form>
      </section>
      <section>
        <h2>法人一覧</h2>
        {data.items.length ? (
          <table>
            <thead>
              <tr>
                <th>法人名</th>
                <th>代表者</th>
                <th>状態</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.representative_name}</td>
                  <td>{c.is_active ? "有効" : "停止"}</td>
                  <td>
                    <Link
                      to="/admin/corporates/$corporateId"
                      params={{ corporateId: c.id }}
                    >
                      管理する
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty />
        )}
        {data.next_cursor && (
          <Link
            className="button secondary"
            to="/admin/corporates"
            search={{ ...search, cursor: data.next_cursor }}
          >
            次のページ
          </Link>
        )}
      </section>
    </>
  );
}
