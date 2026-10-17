import { useSubmission } from "../../../shared/forms/use-submission";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { CorporateListView } from "../../../features/corporates/ui/corporates-list-view";
import { listCorporates } from "../../../features/corporates/api/corporate-api";
export const Route = createFileRoute("/admin/corporates/")({
  validateSearch: (
    s: Record<string, unknown>,
  ): { name?: string; status?: string; cursor?: string } => ({
    name: typeof s.name === "string" ? s.name : "",
    status: typeof s.status === "string" ? s.status : "",
    cursor: typeof s.cursor === "string" ? s.cursor : undefined,
  }),
  loaderDeps: ({ search }) => search,
  beforeLoad: ({ context }) => {
    if (!context.actor.roles.includes("vendor_system_admin"))
      throw new Error("法人一覧を表示する権限がありません。");
  },
  loader: ({ deps, abortController }) =>
    listCorporates(deps, abortController.signal),
  component: Page,
});
function Page() {
  const data = Route.useLoaderData();
  const search = Route.useSearch();
  const navigate = useNavigate();
  const searchSubmission = useSubmission(async (d) => {
    await navigate({
      to: "/admin/corporates",
      search: {
        name: String(d.get("name") || "").trim(),
        status: String(d.get("status") || ""),
        cursor: undefined,
      },
    });
  });
  return (
    <CorporateListView
      key={JSON.stringify(search)}
      data={data}
      search={search}
      onSearch={searchSubmission}
    />
  );
}
