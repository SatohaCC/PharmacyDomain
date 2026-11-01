import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type {
  Store,
  StoreInput,
  StoreDetail,
  StoreNamesInput,
  StoreAddressInput,
  StoreContactInput,
} from "../model/store";

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

export const getStore = (
  corporateId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<StoreDetail> =>
  result(
    api.GET("/corporates/{corporate_id}/stores/{store_id}", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      signal,
    }),
  );

export const updateStoreNames = (
  corporateId: string,
  storeId: string,
  body: StoreNamesInput,
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/stores/{store_id}/names", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body,
    }),
  );

export const updateStoreCode = (
  corporateId: string,
  storeId: string,
  code: string | null,
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/stores/{store_id}/code", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { code },
    }),
  );

export const updateStoreAddress = (
  corporateId: string,
  storeId: string,
  body: StoreAddressInput,
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/stores/{store_id}/address", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { postal_code: body.postal_code, address: body.address },
    }),
  );

export const updateStoreContactInfo = (
  corporateId: string,
  storeId: string,
  body: StoreContactInput,
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/stores/{store_id}/contact-info", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body,
    }),
  );

export const suspendStore = (
  corporateId: string,
  storeId: string,
  reason: string,
) =>
  result(
    api.POST("/corporates/{corporate_id}/stores/{store_id}/suspension", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { reason },
    }),
  );

export const resumeStore = (
  corporateId: string,
  storeId: string,
  reason: string = "営業再開",
) =>
  result(
    api.POST("/corporates/{corporate_id}/stores/{store_id}/resumption", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { reason },
    }),
  );

export const closeStore = (
  corporateId: string,
  storeId: string,
  reason: string,
) =>
  result(
    api.POST("/corporates/{corporate_id}/stores/{store_id}/closure", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { reason },
    }),
  );
