import { createFileRoute, redirect } from "@tanstack/react-router";
import { accessToken } from "../features/auth/api/session";
import {
  currentActor,
  listSelectableStores,
} from "../features/auth/api/actor-api";
import { resolveHomeRedirect } from "../features/auth/api/home-redirect";

export const Route = createFileRoute("/")({
  beforeLoad: async ({ location }) => {
    if (!accessToken()) {
      throw redirect({ to: "/login", search: { returnTo: location.pathname } });
    }
    const target = await resolveHomeRedirect(currentActor, listSelectableStores);
    throw redirect(target);
  },
});
