import { accessToken, oidc, login } from "../../../features/auth/api/session";
import { createFileRoute } from "@tanstack/react-router";

import { AcceptPage } from "../../../features/invitations/ui/accept-page";
export const Route = createFileRoute("/invitations/accept/")({
  component: Page,
});
function Page() {
  return (
    <AcceptPage
      auth={{
        authenticated: !!accessToken(),
        oidcAvailable: !!oidc(),
        login: () => login("/invitations/accept"),
      }}
    />
  );
}
