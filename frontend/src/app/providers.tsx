import { Canvas } from "../shared/ui/Elements";
import {
  useNavigate,
  useRouterState,
  useBlocker,
} from "@tanstack/react-router";
import { NavigationProvider } from "../shared/ui/Link";
import type { ReactNode } from "react";
import { LeaveProvider, useAllowLeave } from "../shared/navigation/leaving";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <LeaveProvider>
      <ApplicationNavigation>{children}</ApplicationNavigation>
    </LeaveProvider>
  );
}
function ApplicationNavigation({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const pathname = useRouterState({
    select: (s) => (s.resolvedLocation ?? s.location).pathname,
  });
  const allowLeave = useAllowLeave();
  useBlocker({ shouldBlockFn: () => !allowLeave(), enableBeforeUnload: false });
  return (
    <NavigationProvider
      pathname={pathname}
      navigate={(href) => {
        void navigate({ href });
      }}
    >
      <Canvas>{children}</Canvas>
    </NavigationProvider>
  );
}
