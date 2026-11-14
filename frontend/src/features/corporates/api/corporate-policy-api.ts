import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { CorporatePolicy } from "../model/corporate-policy";

export const updateCorporatePolicy = (
  corporateId: string,
  body: CorporatePolicy,
) =>
  result(
    api.PUT("/corporates/{corporate_id}/policy", {
      params: { path: { corporate_id: corporateId } },
      body,
    }),
  );
