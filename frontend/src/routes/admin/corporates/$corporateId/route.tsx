import { createFileRoute, Outlet } from "@tanstack/react-router";
import { getCorporate } from "../../../../features/corporates/api/corporate-api";
import { CorporateLayoutView } from "../../../../features/corporates/ui/corporate-layout-view";
export const Route = createFileRoute("/admin/corporates/$corporateId")({
  beforeLoad: ({ params, context }) => {
    if (
      !context.actor.roles.includes("vendor_system_admin") &&
      context.actor.corporate_id !== params.corporateId
    )
      throw new Error("対象が見つかりません。");
  },
  loader: ({ params, abortController }) =>
    getCorporate(params.corporateId, abortController.signal),
  component: CorporateLayout,
});

function CorporateLayout() {
  const corporate = Route.useLoaderData();
  return (
    <CorporateLayoutView corporate={corporate}>
      <Outlet />
    </CorporateLayoutView>
  );
}
