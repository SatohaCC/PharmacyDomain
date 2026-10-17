import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { StoreRegistrationPage } from "../../../../../../features/stores/ui/stores-registration-page";
export const Route = createFileRoute(
  "/admin/corporates/$corporateId/stores/new/",
)({ component: NewStore });

function NewStore() {
  const { corporateId } = Route.useParams();
  const navigate = useNavigate();
  return (
    <StoreRegistrationPage
      corporateId={corporateId}
      onComplete={() =>
        navigate({
          to: "/admin/corporates/$corporateId/stores",
          params: { corporateId },
        })
      }
    />
  );
}
