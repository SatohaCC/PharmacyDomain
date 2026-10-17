import { createFileRoute } from "@tanstack/react-router";
import { CorporateOverviewView } from "../../../../features/corporates/ui/corporates-overview-view";

export const Route = createFileRoute("/admin/corporates/$corporateId/")({
  component: Page,
});
function Page() {
  const { corporateId } = Route.useParams();
  return <CorporateOverviewView corporateId={corporateId} />;
}
