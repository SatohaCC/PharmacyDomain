import { createFileRoute, Link } from "@tanstack/react-router";
import { api, result, corporationParams } from "../shared/api/client";
import { Empty } from "../shared/ui/common";
export const Route = createFileRoute("/admin/corporates/$corporateId/stores/")({
  loader: ({ params, abortController }) =>
    result(
      api.GET("/corporates/{corporate_id}/stores", {
        params: corporationParams(params.corporateId),
        signal: abortController.signal,
      }),
    ),
  component: Stores,
});
function Stores() {
  const data = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  return (
    <section>
      <div className="title">
        <h2>店舗一覧</h2>
        <Link
          className="button"
          to="/admin/corporates/$corporateId/stores/new"
          params={{ corporateId }}
        >
          店舗を登録
        </Link>
      </div>
      {data.length ? (
        <table>
          <thead>
            <tr>
              <th>店舗名</th>
              <th>カナ</th>
              <th>店舗コード</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.name_kana}</td>
                <td>{s.code || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <Empty />
      )}
    </section>
  );
}
