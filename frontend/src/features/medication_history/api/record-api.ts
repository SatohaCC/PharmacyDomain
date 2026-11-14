import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { components, paths } from "../../../shared/api/generated/schema";

export type MedicationHistoryDto =
  components["schemas"]["MedicationHistoryDto"];
export type CategoryCatalogDto = components["schemas"]["CategoryCatalogDto"];
export type StoreCurrentRecordFieldDto =
  paths["/corporates/{corporate_id}/stores/{store_id}/current-record-fields"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type StatutoryRecordSufficiencyDto =
  components["schemas"]["StatutoryRecordSufficiencyDto"];

export const listPatientMedicationHistories = (
  corporateId: string,
  patientId: string,
  signal?: AbortSignal,
): Promise<MedicationHistoryDto[]> =>
  result(
    api.GET(
      "/corporates/{corporate_id}/patients/{patient_id}/medication-histories",
      {
        params: {
          path: { corporate_id: corporateId, patient_id: patientId },
        },
        signal,
      },
    ),
  );

export const getCategoryCatalog = (
  corporateId: string,
  signal?: AbortSignal,
): Promise<CategoryCatalogDto> =>
  result(
    api.GET("/corporates/{corporate_id}/medication-history-category-catalog", {
      params: {
        path: { corporate_id: corporateId },
      },
      signal,
    }),
  );

export const listStoreCurrentRecordFields = (
  corporateId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<StoreCurrentRecordFieldDto[]> =>
  result(
    api.GET("/corporates/{corporate_id}/stores/{store_id}/current-record-fields", {
      params: {
        path: { corporate_id: corporateId, store_id: storeId },
      },
      signal,
    }),
  );

export const verifyStatutoryRecord = (
  corporateId: string,
  recordId: string,
  signal?: AbortSignal,
): Promise<StatutoryRecordSufficiencyDto> =>
  result(
    api.GET(
      "/corporates/{corporate_id}/medication-histories/{record_id}/statutory-record-sufficiency",
      {
        params: {
          path: { corporate_id: corporateId, record_id: recordId },
        },
        signal,
      },
    ),
  );

export const updateCategoryCatalog = (
  corporateId: string,
  body: components["schemas"]["UpdateCategoryCatalogRequest"],
  signal?: AbortSignal,
): Promise<CategoryCatalogDto> =>
  result(
    api.PUT("/corporates/{corporate_id}/medication-history-category-catalog", {
      params: { path: { corporate_id: corporateId } },
      body,
      signal,
    }),
  );

export const saveStoreCurrentRecordFields = (
  corporateId: string,
  storeId: string,
  fields: components["schemas"]["SaveStoreCurrentRecordFieldsRequest"]["fields"],
  signal?: AbortSignal,
) =>
  result(
    api.PUT("/corporates/{corporate_id}/stores/{store_id}/current-record-fields", {
      params: { path: { corporate_id: corporateId, store_id: storeId } },
      body: { fields },
      signal,
    }),
  );
