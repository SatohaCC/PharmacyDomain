import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { UserList } from "../model/user";
export const listUsers = (
  id: string,
  cursor?: string,
  signal?: AbortSignal,
): Promise<UserList> =>
  result(
    api.GET("/corporates/{corporate_id}/users", {
      params: { ...corporationParams(id), query: { cursor } },
      signal,
    }),
  );
export const registrationOptions = async (id: string, signal?: AbortSignal) => {
  const options = { params: corporationParams(id), signal };
  const [stores, staffs] = await Promise.all([
    result(api.GET("/corporates/{corporate_id}/stores", options)),
    result(api.GET("/corporates/{corporate_id}/staffs", options)),
  ]);
  return { stores, staffs };
};
