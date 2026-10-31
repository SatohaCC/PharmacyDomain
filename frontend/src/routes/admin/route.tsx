import {
  createFileRoute,
  Outlet,
  redirect,
  useRouter,
  useRouterState,
} from "@tanstack/react-router";
import { AdminShell } from "../../app/admin-shell";
import { accessToken, setAccessToken } from "../../features/auth/api/session";
import { currentActor, listSelectableStores } from "../../features/auth/api/actor-api";
import { selectStoreContext } from "../../features/auth/api/local-authentication";
import { StoreContextSelectorView } from "../../features/stores/ui/store-context-selector-view";

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
    const selectableStores = actor.roles.includes("vendor_system_admin")
      ? []
      : await listSelectableStores();
    return { actor, selectableStores };
  },
  component: Admin,
});

function Admin() {
  const { actor, selectableStores } = Route.useRouteContext();
  const router = useRouter();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const handleSelectStore = async (storeId: string) => {
    const session = await selectStoreContext(storeId);
    setAccessToken(session.access_token);
    await router.invalidate();
  };

  const storeSelector =
    selectableStores.length > 0 ? (
      <StoreContextSelectorView
        stores={selectableStores}
        selectedStoreId={actor.selected_store_id ?? null}
        onSelectStore={(id) => void handleSelectStore(id)}
      />
    ) : undefined;

  return (
    <AdminShell actor={actor} storeSelector={storeSelector}>
      <div key={pathname}>
        <Outlet />
      </div>
    </AdminShell>
  );
}
