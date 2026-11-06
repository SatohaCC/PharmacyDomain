import { createFileRoute, useRouter } from "@tanstack/react-router";
import { StoreDetailPage } from "../../../../../../features/stores/ui/store-detail-page";
import { getStore } from "../../../../../../features/stores/api/store-api";

export const Route = createFileRoute(
  "/admin/corporates/$corporateId/stores/$storeId/",
)({
  loader: ({ params, abortController }) =>
    getStore(params.corporateId, params.storeId, abortController.signal),
  component: Page,
});

function Page() {
  const store = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  const router = useRouter();

  return (
    <StoreDetailPage
      store={store}
      corporateId={corporateId}
      onRefresh={async () => {
        await router.invalidate();
      }}
    />
  );
}
