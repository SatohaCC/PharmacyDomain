import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { CorporateOverviewView } from "../../../../features/corporates/ui/corporates-overview-view";

const parentRoute = getRouteApi("/admin/corporates/$corporateId");

export const Route = createFileRoute("/admin/corporates/$corporateId/")({
  component: Page,
});
function Page() {
  const corporate = parentRoute.useLoaderData();
  return <CorporateOverviewView corporate={corporate} />;
}
