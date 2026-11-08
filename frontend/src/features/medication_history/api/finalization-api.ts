import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { FinalizeMedicationHistoryInput } from "../model/finalization";

export const finalizeMedicationHistory = (
  corporateId: string,
  recordId: string,
  input: FinalizeMedicationHistoryInput,
  signal?: AbortSignal,
) =>
  result(
    api.POST(
      "/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
      {
        params: {
          path: { corporate_id: corporateId, record_id: recordId },
        },
        body: input,
        signal,
      },
    ),
  );
