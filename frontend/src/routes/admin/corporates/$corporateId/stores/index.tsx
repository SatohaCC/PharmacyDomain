import { createFileRoute } from "@tanstack/react-router";
import { StoreListView } from "../../../../../features/stores/ui/stores-list-view";
import { listStores } from "../../../../../features/stores/api/store-api";
export const Route = createFileRoute("/admin/corporates/$corporateId/stores/")({
  loader: ({ params, abortController }) =>
    listStores(params.corporateId, abortController.signal),
  component: Page,
});
function Page() {
  const data = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  return <StoreListView data={data} corporateId={corporateId} />;
}
