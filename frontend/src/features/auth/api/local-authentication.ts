import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { paths } from "../../../shared/api/generated/schema";

export type LoginSessionDto =
  paths["/auth/login"]["post"]["responses"]["200"]["content"]["application/json"];

export const passwordLogin = (
  corporateId: string,
  login_id: string,
  password: string,
): Promise<LoginSessionDto> =>
  result(
    api.POST("/auth/login", {
      body: { corporate_id: corporateId, login_id, password },
    }),
  );

export const changeInitialPassword = (
  token: string,
  password: string,
): Promise<LoginSessionDto> =>
  result(
    api.POST("/auth/password", {
      headers: { Authorization: `Bearer ${token}` },
      body: { password },
    }),
  );

export const selectStoreContext = (storeId: string): Promise<LoginSessionDto> =>
  result(
    api.POST("/auth/store-context", {
      body: { store_id: storeId },
    }),
  );

export const endLocalSession = () => result(api.POST("/auth/logout"));

export const vendorPasswordLogin = (
  login_id: string,
  password: string,
): Promise<LoginSessionDto> =>
  result(api.POST("/auth/vendor/login", { body: { login_id, password } }));
