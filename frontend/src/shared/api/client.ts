import createClient from "openapi-fetch";
import type { paths } from "./generated/schema";
export const api = createClient<paths>({ baseUrl: "/api" });
let getToken: () => string = () => "";
export function configureApi(tokenProvider: () => string) {
  getToken = tokenProvider;
}
api.use({
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
});
export function corporationParams(corporateId: string) {
  return { path: { corporate_id: corporateId } };
}
