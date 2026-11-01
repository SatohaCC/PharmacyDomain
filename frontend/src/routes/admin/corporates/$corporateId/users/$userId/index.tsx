import { createFileRoute, useRouter } from "@tanstack/react-router";
import { UserDetailPage } from "../../../../../../features/users/ui/user-detail-page";
import { getUser, getStaff } from "../../../../../../features/users/api/user-api";
import { listStores } from "../../../../../../features/stores/api/store-api";
import type { UserDetail, StaffDetail } from "../../../../../../features/users/model/user";

export const Route = createFileRoute(
  "/admin/corporates/$corporateId/users/$userId/",
)({
  loader: async ({ params, abortController }) => {
    const membership = await getUser(
      params.corporateId,
      params.userId,
      abortController.signal,
    );
    let staff: StaffDetail | null = null;
    if (membership.staff_id) {
      try {
        staff = await getStaff(
          params.corporateId,
          membership.staff_id,
          abortController.signal,
        );
      } catch {
        staff = null;
      }
    }
    const stores = await listStores(
      params.corporateId,
      abortController.signal,
    );
    const userDetail: UserDetail = {
      id: membership.id,
      account_id: membership.account_id,
      person_id: membership.person_id,
      corporate_id: membership.corporate_id,
      role: membership.role,
      status: membership.status,
      account_status: membership.account_status,
      store_ids: membership.store_ids,
      staff_id: membership.staff_id,
      staff,
    };
    return {
      user: userDetail,
      availableStores: stores.map((s) => ({ id: s.id, name: s.name })),
    };
  },
  component: Page,
});

function Page() {
  const { user, availableStores } = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  const router = useRouter();

  return (
    <UserDetailPage
      user={user}
      corporateId={corporateId}
      availableStores={availableStores}
      onRefresh={async () => {
        await router.invalidate();
      }}
    />
  );
}
