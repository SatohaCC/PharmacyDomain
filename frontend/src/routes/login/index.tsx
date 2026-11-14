import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { safeReturnPath } from "../../shared/navigation/paths";
import { LoginPage } from "../../features/auth/components/LoginPage";

export const Route = createFileRoute("/login/")({
  validateSearch: (s: Record<string, unknown>) => ({
    returnTo: safeReturnPath(s.returnTo, {
      fallbackPath: "/admin",
      allowedPrefixes: ["/admin", "/stores"],
    }),
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
