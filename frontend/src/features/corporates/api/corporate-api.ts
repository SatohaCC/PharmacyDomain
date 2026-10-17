import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type {
  Corporate,
  CorporateInput,
  CorporateList,
  CorporateSearch,
} from "../model/corporate";
export const createCorporate = (body: CorporateInput) =>
  result(api.POST("/corporates", { body }));
export const getCorporate = (
  id: string,
  signal?: AbortSignal,
): Promise<Corporate> =>
  result(
    api.GET("/corporates/{corporate_id}", {
      params: corporationParams(id),
      signal,
    }),
  );
export const listCorporates = (
  search: CorporateSearch,
  signal?: AbortSignal,
): Promise<CorporateList> =>
  result(
    api.GET("/corporates", {
      params: {
        query: {
          name: search.name || undefined,
          status: search.status || undefined,
          cursor: search.cursor,
        },
      },
      signal,
    }),
  );
