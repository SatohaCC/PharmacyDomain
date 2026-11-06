import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
export type { StoreAffiliation } from "../model/store-work-conditions";

export const getWorkConditions = (
  corporateId: string,
  staffId: string,
  storeId: string | undefined,
  appliedOn: string,
  signal?: AbortSignal,
) =>
  result(
    api.GET("/corporates/{corporate_id}/staffs/{staff_id}/work-conditions", {
      params: {
        path: { corporate_id: corporateId, staff_id: staffId },
        query: { store_id: storeId, applied_on: appliedOn },
      },
      signal,
    }),
  );
