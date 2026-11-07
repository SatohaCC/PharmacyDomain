import {
  createFileRoute,
  Outlet,
  redirect,
  useNavigate,
  useRouter,
  useRouterState,
} from "@tanstack/react-router";
import { StoreShell } from "../../../app/store-shell";
import { accessToken, setAccessToken } from "../../../features/auth/api/session";
import {
  currentActor,
  listSelectableStores,
} from "../../../features/auth/api/actor-api";
import { selectStoreContext } from "../../../features/auth/api/local-authentication";
import { StoreContextSelectorView } from "../../../features/stores/ui/store-context-selector-view";

export const Route = createFileRoute("/stores/$storeId")({
  beforeLoad: async ({ params, location }) => {
    if (!accessToken()) {
      throw redirect({ to: "/login", search: { returnTo: location.pathname } });
    }
    let actor = await currentActor();
    const selectableStores = actor.roles.includes("vendor_system_admin")
      ? []
      : await listSelectableStores();

    // 店舗コンテキストの同期（未選択または別店舗が指定されている場合）
    if (actor.selected_store_id !== params.storeId) {
      try {
        const session = await selectStoreContext(params.storeId);
        setAccessToken(session.access_token);
        actor = await currentActor();
      } catch {
        // 店舗切替不可の場合はそのまま進む（権限エラーは各ユースケースで検知）
      }
    }

    const currentStore = selectableStores.find((s) => s.id === params.storeId);

    return { actor, selectableStores, currentStore };
  },
  component: StoreRouteComponent,
});

function StoreRouteComponent() {
  const { storeId } = Route.useParams();
  const { actor, selectableStores, currentStore } = Route.useRouteContext();
  const router = useRouter();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const handleSelectStore = async (targetStoreId: string) => {
    if (targetStoreId === storeId) return;
    const session = await selectStoreContext(targetStoreId);
    setAccessToken(session.access_token);
    await router.invalidate();
    await navigate({
      to: "/stores/$storeId/patients",
      params: { storeId: targetStoreId },
    });
  };

  const storeSelector =
    selectableStores.length > 0 ? (
      <StoreContextSelectorView
        stores={selectableStores}
        selectedStoreId={storeId}
        onSelectStore={(id) => void handleSelectStore(id)}
      />
    ) : undefined;

  return (
    <StoreShell
      storeId={storeId}
      storeName={currentStore?.name}
      actor={actor}
      storeSelector={storeSelector}
    >
      <div key={pathname}>
        <Outlet />
      </div>
    </StoreShell>
  );
}
