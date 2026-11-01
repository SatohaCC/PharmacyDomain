import { api, corporationParams } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { UserList, StaffDetail } from "../model/user";
import type { paths, components } from "../../../shared/api/generated/schema";

export type MembershipDto =
  paths["/corporates/{corporate_id}/users/{membership_id}"]["get"]["responses"]["200"]["content"]["application/json"];

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

export const getUser = (
  corporateId: string,
  membershipId: string,
  signal?: AbortSignal,
): Promise<MembershipDto> =>
  result(
    api.GET("/corporates/{corporate_id}/users/{membership_id}", {
      params: {
        path: { corporate_id: corporateId, membership_id: membershipId },
      },
      signal,
    }),
  );

export const getStaff = (
  corporateId: string,
  staffId: string,
  signal?: AbortSignal,
): Promise<StaffDetail> =>
  result(
    api.GET("/corporates/{corporate_id}/staffs/{staff_id}", {
      params: { path: { corporate_id: corporateId, staff_id: staffId } },
      signal,
    }),
  ) as Promise<StaffDetail>;

export const updateMembership = (
  corporateId: string,
  membershipId: string,
  body: {
    role?: components["schemas"]["MembershipRole-Input"] | null;
    store_ids?: string[] | null;
  },
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/users/{membership_id}", {
      params: {
        path: { corporate_id: corporateId, membership_id: membershipId },
      },
      body,
    }),
  );

export const suspendUser = (corporateId: string, membershipId: string) =>
  result(
    api.POST("/corporates/{corporate_id}/users/{membership_id}/suspension", {
      params: {
        path: { corporate_id: corporateId, membership_id: membershipId },
      },
    }),
  );

export const reactivateUser = (corporateId: string, membershipId: string) =>
  result(
    api.POST("/corporates/{corporate_id}/users/{membership_id}/reactivation", {
      params: {
        path: { corporate_id: corporateId, membership_id: membershipId },
      },
    }),
  );

export const updateStaffNames = (
  corporateId: string,
  staffId: string,
  body: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  },
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/staffs/{staff_id}/names", {
      params: { path: { corporate_id: corporateId, staff_id: staffId } },
      body,
    }),
  );

export const updateStaffJobTitle = (
  corporateId: string,
  staffId: string,
  jobTitle: string | null,
) =>
  result(
    api.PATCH("/corporates/{corporate_id}/staffs/{staff_id}/job-title", {
      params: { path: { corporate_id: corporateId, staff_id: staffId } },
      body: { job_title: jobTitle },
    }),
  );

export const registrationOptions = async (id: string, signal?: AbortSignal) => {
  const options = { params: corporationParams(id), signal };
  const stores = await result(
    api.GET("/corporates/{corporate_id}/stores", options),
  );
  return { stores };
};
