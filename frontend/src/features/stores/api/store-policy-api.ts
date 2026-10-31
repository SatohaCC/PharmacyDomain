import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { EffectivePolicy, StorePolicy } from "../model/store-policy";

function storeParams(corporateId: string, storeId: string) {
  return { path: { corporate_id: corporateId, store_id: storeId } };
}

export const updateStorePolicy = (
  corporateId: string,
  storeId: string,
  body: StorePolicy,
) =>
  result(
    api.PUT("/corporates/{corporate_id}/stores/{store_id}/policy", {
      params: storeParams(corporateId, storeId),
      body,
    }),
  );

export const getEffectivePolicy = (
  corporateId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<EffectivePolicy> =>
  result(
    api.GET("/corporates/{corporate_id}/stores/{store_id}/effective-policy", {
      params: storeParams(corporateId, storeId),
      signal,
    }),
  );
