import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type {
  MedicationHistoryBlock,
  MedicationHistoryBlockInput,
} from "../model/block";

export const listMedicationHistoryBlocks = (
  corporateId: string,
  recordId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<MedicationHistoryBlock[]> =>
  result(
    api.GET(
      "/corporates/{corporate_id}/medication-histories/{record_id}/blocks",
      {
        params: {
          path: { corporate_id: corporateId, record_id: recordId },
          query: { store_id: storeId },
        },
        signal,
      },
    ),
  );

export const saveMedicationHistoryBlocks = (
  corporateId: string,
  recordId: string,
  storeId: string,
  blocks: MedicationHistoryBlockInput[],
  signal?: AbortSignal,
): Promise<MedicationHistoryBlock[]> =>
  result(
    api.PUT(
      "/corporates/{corporate_id}/medication-histories/{record_id}/blocks",
      {
        params: {
          path: { corporate_id: corporateId, record_id: recordId },
        },
        body: {
          store_id: storeId,
          blocks: blocks.map((b) => ({
            category_code: b.category_code,
            content: b.content,
            display_order: b.display_order,
            id: b.id ?? null,
            source_module: b.source_module ?? "soap",
            source_id: b.source_id ?? null,
          })),
        },
        signal,
      },
    ),
  );

export const listReceptionBlocks = (
  corporateId: string,
  receptionId: string,
  storeId: string,
  signal?: AbortSignal,
): Promise<MedicationHistoryBlock[]> =>
  result(
    api.GET("/corporates/{corporate_id}/receptions/{reception_id}/blocks", {
      params: {
        path: { corporate_id: corporateId, reception_id: receptionId },
        query: { store_id: storeId },
      },
      signal,
    }),
  );

export const saveReceptionBlocks = (
  corporateId: string,
  receptionId: string,
  storeId: string,
  blocks: MedicationHistoryBlockInput[],
  signal?: AbortSignal,
): Promise<MedicationHistoryBlock[]> =>
  result(
    api.PUT("/corporates/{corporate_id}/receptions/{reception_id}/blocks", {
      params: {
        path: { corporate_id: corporateId, reception_id: receptionId },
      },
      body: {
        store_id: storeId,
        blocks: blocks.map((b) => ({
          category_code: b.category_code,
          content: b.content,
          display_order: b.display_order,
          id: b.id ?? null,
          source_module: b.source_module ?? "soap",
          source_id: b.source_id ?? null,
        })),
      },
      signal,
    }),
  );
