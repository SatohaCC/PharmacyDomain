import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router";
import { AdminShell } from "../../app/admin-shell";
import { accessToken } from "../../features/auth/api/session";
import { currentActor } from "../../features/auth/api/actor-api";
export const Route = createFileRoute("/admin")({
  beforeLoad: async ({ location }) => {
    if (!accessToken())
      throw redirect({ to: "/login", search: { returnTo: location.pathname } });
    const actor = await currentActor();
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
    <AdminShell actor={actor}>
      <div key={pathname}>
        <Outlet />
      </div>
    </AdminShell>
  );
}
