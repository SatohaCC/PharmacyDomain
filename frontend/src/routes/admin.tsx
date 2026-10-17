import {
  createFileRoute,
  Outlet,
  Link,
  redirect,
  useRouterState,
} from "@tanstack/react-router";
import { api, result } from "../shared/api/client";
import { accessToken, logout } from "../shared/auth/session";
export const Route = createFileRoute("/admin")({
  beforeLoad: async ({ location }) => {
    if (!accessToken())
      throw redirect({ to: "/login", search: { returnTo: location.pathname } });
    const actor = await result(api.GET("/me"));
    if (
      !actor.roles.some(
        (r) => r === "vendor_system_admin" || r === "corporate_admin",
      )
    )
      throw new Error("管理画面を操作する権限がありません。");
    return { actor };
  },
  component: Admin,
});
function Admin() {
  const { actor } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/admin">
          薬局管理<span>Administration</span>
        </a>
        <nav aria-label="管理メニュー">
          {actor.roles.includes("vendor_system_admin") ? (
            <Link to="/admin/corporates">法人管理</Link>
          ) : (
            actor.corporate_id && (
              <Link
                to="/admin/corporates/$corporateId"
                params={{ corporateId: actor.corporate_id }}
              >
                自法人の管理
              </Link>
            )
          )}
          <button className="quiet" onClick={() => void logout()}>
            ログアウト
          </button>
        </nav>
        <small>操作範囲はログイン権限に従います</small>
      </aside>
      <main key={pathname}>
        <header>
          <span className="eyebrow">ADMIN CONSOLE</span>
          <span className="badge">
            {actor.roles.includes("vendor_system_admin")
              ? "システム管理者"
              : "法人管理者"}
          </span>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
