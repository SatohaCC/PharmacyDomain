import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { RegistrationInput } from "../model/registration-input";
import type { UserRole } from "../model/registration";

export async function registerUser(
  corporateId: string,
  input: RegistrationInput,
  role: UserRole,
) {
  const params = corporationParams(corporateId);
  const { names, storeIds } = input;
  const res = await result(
    api.POST("/corporates/{corporate_id}/staffs", {
      params,
      body: {
        ...names,
        is_registered_dietitian: true,
        initial_home_store_id: input.homeStore || undefined,
        initial_start_date: input.startDate || undefined,
        account: {
          email: input.email,
          password: input.initialPassword,
          role,
          store_ids: storeIds.length > 0 ? storeIds : undefined,
        },
      },
    }),
  );
  return { id: res.staff_id, email: res.email };
}
