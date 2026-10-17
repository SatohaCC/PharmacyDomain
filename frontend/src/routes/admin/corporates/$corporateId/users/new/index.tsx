import { createFileRoute } from "@tanstack/react-router";
import { registrationOptions } from "../../../../../../features/users/api/user-api";
import { UserRegistrationPage } from "../../../../../../features/users/ui/user-registration-page";
export const Route = createFileRoute(
  "/admin/corporates/$corporateId/users/new/",
)({
  loader: ({ params, abortController }) =>
    registrationOptions(params.corporateId, abortController.signal),
  component: Invite,
});
function Invite() {
  const { corporateId } = Route.useParams();
  const options = Route.useLoaderData();
  return (
    <UserRegistrationPage
      key={corporateId}
      corporateId={corporateId}
      options={options}
    />
  );
}
