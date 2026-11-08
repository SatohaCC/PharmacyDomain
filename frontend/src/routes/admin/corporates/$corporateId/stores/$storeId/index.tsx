import { createFileRoute, useRouter } from "@tanstack/react-router";
import { StoreDetailPage } from "../../../../../../features/stores/ui/store-detail-page";
import {
  getStore,
  listStoreManagerAssignments,
} from "../../../../../../features/stores/api/store-api";
import { listUsers } from "../../../../../../features/users/api/user-api";

export const Route = createFileRoute(
  "/admin/corporates/$corporateId/stores/$storeId/",
)({
  loader: async ({ params, abortController }) => {
    const [store, managersRes, usersRes] = await Promise.all([
      getStore(params.corporateId, params.storeId, abortController.signal),
      listStoreManagerAssignments(
        params.corporateId,
        params.storeId,
        abortController.signal,
      ).catch(() => ({ items: [] })),
      listUsers(
        params.corporateId,
        undefined,
        abortController.signal,
        params.storeId,
      ).catch(() => ({ items: [] })),
    ]);
    return {
      store,
      managers: managersRes.items,
      staffUsers: usersRes.items,
    };
  },
  component: Page,
});

function Page() {
  const { store, managers, staffUsers } = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  const router = useRouter();

  return (
    <StoreDetailPage
      store={store}
      corporateId={corporateId}
      managers={managers}
      staffUsers={staffUsers}
      onRefresh={async () => {
        await router.invalidate();
      }}
    />
  );
}
