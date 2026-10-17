import { configureApi } from "../shared/api/client";
import { accessToken } from "../features/auth/api/session";
export function configureApplication() {
  configureApi(accessToken);
}
