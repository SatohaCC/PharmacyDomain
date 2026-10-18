import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";

export const passwordLogin = (loginId: string, password: string) =>
  result(api.POST("/auth/login", { body: { login_id: loginId, password } }));

export const changeInitialPassword = (token: string, password: string) =>
  result(
    api.POST("/auth/password", {
      headers: { Authorization: `Bearer ${token}` },
      body: { password },
    }),
  );

export const endLocalSession = () => result(api.POST("/auth/logout"));
