import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { Store, StoreInput } from "../model/store";
export const createStore = (id: string, body: StoreInput) =>
  result(
    api.POST("/corporates/{corporate_id}/stores", {
      params: corporationParams(id),
      body,
    }),
  );
export const listStores = (
  id: string,
  signal?: AbortSignal,
): Promise<Store[]> =>
  result(
    api.GET("/corporates/{corporate_id}/stores", {
      params: corporationParams(id),
      signal,
    }),
  );
