import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type {
  Corporate,
  CorporateInput,
  CorporateList,
  CorporateSearch,
} from "../model/corporate";
export const createCorporate = (body: CorporateInput) =>
  result(
    api.POST("/corporates", {
      body: {
        ...body,
        corporate_type: body.corporate_type || "stock_company",
      },
    }),
  );
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

export const registerContract = (body: {
  name: string;
  representative_last_name: string;
  representative_first_name: string;
  administrator: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  };
  email: string;
  initial_password: string;
}) => result(api.POST("/contracts", { body }));
