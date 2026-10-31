import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { paths } from "../../../shared/api/generated/schema";

export type CurrentActorDto =
  paths["/me"]["get"]["responses"]["200"]["content"]["application/json"];

export type SelectableStoreDto =
  paths["/me/stores"]["get"]["responses"]["200"]["content"]["application/json"][number];

export const currentActor = (signal?: AbortSignal) =>
  result(api.GET("/me", { signal }));

export const listSelectableStores = (
  signal?: AbortSignal,
): Promise<SelectableStoreDto[]> => result(api.GET("/me/stores", { signal }));
