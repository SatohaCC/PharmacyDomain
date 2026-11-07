import { createFileRoute, redirect } from "@tanstack/react-router";
import { accessToken } from "../features/auth/api/session";
import {
  currentActor,
  listSelectableStores,
} from "../features/auth/api/actor-api";

export const Route = createFileRoute("/")({
  beforeLoad: async ({ location }) => {
    if (!accessToken()) {
      throw redirect({ to: "/login", search: { returnTo: location.pathname } });
    }
    try {
      const actor = await currentActor();
      if (actor.selected_store_id) {
        throw redirect({
          to: "/stores/$storeId/patients",
          params: { storeId: actor.selected_store_id },
        });
      }
      if (!actor.roles.includes("vendor_system_admin")) {
        const stores = await listSelectableStores().catch(() => []);
        if (stores.length > 0) {
          throw redirect({
            to: "/stores/$storeId/patients",
            params: { storeId: stores[0].id },
          });
        }
      }
    } catch (e) {
      if (typeof e === "object" && e !== null && "to" in e) {
        throw e;
      }
    }
    throw redirect({ to: "/admin" });
  },
});
