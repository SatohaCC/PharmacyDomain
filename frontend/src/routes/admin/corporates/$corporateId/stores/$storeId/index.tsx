import { createFileRoute, useRouter } from "@tanstack/react-router";
import { StoreDetailPage } from "../../../../../../features/stores/components/StoreDetailPage";
import {
  getStore,
  listStoreManagerAssignments,
} from "../../../../../../features/stores/api/store-api";
import {
  listStaffs,
  listUsers,
} from "../../../../../../features/users/api/user-api";

export const Route = createFileRoute(
  "/admin/corporates/$corporateId/stores/$storeId/",
)({
  loader: async ({ params, abortController }) => {
    const [store, managersRes, usersRes, staffs] = await Promise.all([
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
      listStaffs(params.corporateId, abortController.signal).catch(() => []),
    ]);
    return {
      store,
      managers: managersRes.items,
      staffUsers: usersRes.items,
      staffs,
    };
  },
  component: Page,
});

function Page() {
  const { store, managers, staffUsers, staffs } = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  const router = useRouter();

  return (
    <StoreDetailPage
      store={store}
      corporateId={corporateId}
      managers={managers}
      staffUsers={staffUsers}
      staffs={staffs}
      onRefresh={async () => {
        await router.invalidate();
      }}
    />
  );
}
