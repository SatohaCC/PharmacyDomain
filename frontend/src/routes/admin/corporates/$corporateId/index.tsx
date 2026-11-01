import { createFileRoute, getRouteApi, useRouter } from "@tanstack/react-router";
import { CorporateOverviewPage } from "../../../../features/corporates/ui/corporates-overview-page";

const parentRoute = getRouteApi("/admin/corporates/$corporateId");

export const Route = createFileRoute("/admin/corporates/$corporateId/")({
  component: Page,
});
function Page() {
  const corporate = parentRoute.useLoaderData();
  const router = useRouter();
  return (
    <CorporateOverviewPage
      corporate={corporate}
      onRefresh={async () => {
        await router.invalidate();
      }}
    />
  );
}
