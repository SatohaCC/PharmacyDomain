import { useCallback } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { CallbackPage } from "../../../features/auth/ui/callback-page";
export const Route = createFileRoute("/auth/callback/")({ component: Page });
function Page() {
  const navigate = useNavigate();
  const onNavigate = useCallback(
    (href: string) => navigate({ href }),
    [navigate],
  );
  return <CallbackPage navigate={onNavigate} />;
}
