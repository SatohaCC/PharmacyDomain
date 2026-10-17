import { createFileRoute, Link } from "@tanstack/react-router";
import { api, result, corporationParams } from "../shared/api/client";
import { Empty } from "../shared/ui/common";
export const Route = createFileRoute("/admin/corporates/$corporateId/users/")({
  validateSearch: (s: Record<string, unknown>): { cursor?: string } => ({
    cursor: typeof s.cursor === "string" ? s.cursor : undefined,
  }),
  loaderDeps: ({ search }) => search,
  loader: ({ params, deps, abortController }) =>
    result(
      api.GET("/corporates/{corporate_id}/users", {
        params: {
          ...corporationParams(params.corporateId),
          query: { cursor: deps.cursor },
        },
        signal: abortController.signal,
      }),
    ),
  component: Users,
});
const roles: Record<string, string> = {
  corporate_admin: "法人管理者",
  store_operator: "店舗操作者",
  store_viewer: "店舗閲覧者",
};
function Users() {
  const data = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  return (
    <section>
      <div className="title">
        <h2>ユーザー一覧</h2>
        <Link
          className="button"
          to="/admin/corporates/$corporateId/users/new"
          params={{ corporateId }}
        >
          ユーザーを招待
        </Link>
      </div>
      <p>招待を受諾したユーザーを表示します。</p>
      {data.items.length ? (
        <table>
          <thead>
            <tr>
              <th>本人ID</th>
              <th>権限</th>
              <th>法人権限</th>
              <th>アカウント</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((u) => (
              <tr key={u.id}>
                <td className="identifier">{u.person_id}</td>
                <td>{roles[u.role] || u.role}</td>
                <td>{u.status === "active" ? "有効" : "停止"}</td>
                <td>{u.account_status === "active" ? "有効" : "停止"}</td>
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
          to="/admin/corporates/$corporateId/users"
          params={{ corporateId }}
          search={{ cursor: data.next_cursor }}
        >
          次のページ
        </Link>
      )}
    </section>
  );
}
