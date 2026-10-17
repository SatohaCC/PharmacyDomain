import { createFileRoute } from "@tanstack/react-router";
import { UserListView } from "../../../../../features/users/ui/users-list-view";
import { listUsers } from "../../../../../features/users/api/user-api";
export const Route = createFileRoute("/admin/corporates/$corporateId/users/")({
  validateSearch: (s: Record<string, unknown>): { cursor?: string } => ({
    cursor: typeof s.cursor === "string" ? s.cursor : undefined,
  }),
  loaderDeps: ({ search }) => search,
  loader: ({ params, deps, abortController }) =>
    listUsers(params.corporateId, deps.cursor, abortController.signal),
  component: Page,
});
function Page() {
  const data = Route.useLoaderData();
  const { corporateId } = Route.useParams();
  return <UserListView data={data} corporateId={corporateId} />;
}
