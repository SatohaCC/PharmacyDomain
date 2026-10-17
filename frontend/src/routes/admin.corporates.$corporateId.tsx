import { createFileRoute, Outlet, Link } from "@tanstack/react-router";
import { api, result, corporationParams } from "../shared/api/client";
export const Route = createFileRoute("/admin/corporates/$corporateId")({
  beforeLoad: ({ params, context }) => {
    if (
      !context.actor.roles.includes("vendor_system_admin") &&
      context.actor.corporate_id !== params.corporateId
    )
      throw new Error("対象が見つかりません。");
  },
  loader: ({ params, abortController }) =>
    result(
      api.GET("/corporates/{corporate_id}", {
        params: corporationParams(params.corporateId),
        signal: abortController.signal,
      }),
    ),
  component: CorporateLayout,
});
function CorporateLayout() {
  const c = Route.useLoaderData();
  return (
    <>
      <div className="title">
        <div>
          <h1>{c.name}</h1>
          <p>
            代表者 {c.representative_name} · {c.is_active ? "有効" : "停止中"}
          </p>
        </div>
      </div>
      <nav className="tabs" aria-label="法人管理">
        <Link
          to="/admin/corporates/$corporateId"
          params={{ corporateId: c.id }}
        >
          概要
        </Link>
        <Link
          to="/admin/corporates/$corporateId/stores"
          params={{ corporateId: c.id }}
        >
          店舗
        </Link>
        <Link
          to="/admin/corporates/$corporateId/users"
          params={{ corporateId: c.id }}
        >
          ユーザー
        </Link>
      </nav>
      <Outlet />
    </>
  );
}
