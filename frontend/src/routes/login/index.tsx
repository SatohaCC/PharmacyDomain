import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { safeReturnPath } from "../../shared/navigation/paths";
import { LoginPage } from "../../features/auth/ui/login-page";
export const Route = createFileRoute("/login/")({
  validateSearch: (s: Record<string, unknown>) => ({
    returnTo: safeReturnPath(s.returnTo),
  }),
  component: Page,
});
function Page() {
  const { returnTo } = Route.useSearch();
  const navigate = useNavigate();
  return (
    <LoginPage returnTo={returnTo} navigate={(href) => navigate({ href })} />
  );
}
