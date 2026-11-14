import type { CurrentActorDto, SelectableStoreDto } from "./actor-api";

export type HomeRedirectTarget =
  | { to: "/stores/$storeId/patients"; params: { storeId: string } }
  | { to: "/admin" };

/** ログイン済みアクターの権限と所属店舗に応じてホーム遷移先を決める。 */
export async function resolveHomeRedirect(
  loadActor: () => Promise<CurrentActorDto>,
  loadStores: () => Promise<SelectableStoreDto[]>,
): Promise<HomeRedirectTarget> {
  const actor = await loadActor().catch(() => null);
  if (!actor) {
    return { to: "/admin" };
  }
  if (actor.selected_store_id) {
    return {
      to: "/stores/$storeId/patients",
      params: { storeId: actor.selected_store_id },
    };
  }
  if (!actor.roles.includes("vendor_system_admin")) {
    const stores = await loadStores().catch(() => []);
    if (stores.length > 0) {
      return {
        to: "/stores/$storeId/patients",
        params: { storeId: stores[0].id },
      };
    }
  }
  return { to: "/admin" };
}
