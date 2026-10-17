import { api, corporationParams } from "../../../shared/api/client";
import { ApiError, result } from "../../../shared/api/errors";
import type { InvitationInput } from "../model/invitation-input";
import {
  prepareInvitation,
  type RegistrationProgress,
} from "../model/prepare-invitation";
import type { UserRole } from "../model/registration";

export async function issueInvitation(
  corporateId: string,
  input: InvitationInput,
  personMode: string,
  role: UserRole,
  staffMode: string,
  p: RegistrationProgress,
  changed: () => void,
) {
  const params = corporationParams(corporateId);

  const { names, storeIds } = input;
  if (personMode === "existing" && !p.personId) {
    p.personId = input.personId;
    if (!p.personId) throw new Error("本人IDを指定してください。");
  }
  const prepared = await prepareInvitation(
    p,
    {
      isUncertain: (e) => e instanceof ApiError && e.uncertain,
      createPerson: async () =>
        (
          await result(
            api.POST("/corporates/{corporate_id}/people", {
              params,
              body: names,
            }),
          )
        ).id,
      prepareStaff:
        role === "corporate_admin"
          ? undefined
          : async (personId) => {
              if (staffMode === "existing" && !p.linked) {
                p.staffId = input.staffId;
                changed();
              }
              if (!p.staffId) {
                if (staffMode === "existing") {
                  p.staffId = input.staffId;
                  if (!p.staffId)
                    throw new Error("スタッフを選択してください。");
                } else {
                  p.staffId = (
                    await result(
                      api.POST("/corporates/{corporate_id}/staffs", {
                        params,
                        body: {
                          ...names,
                          is_registered_dietitian: true,
                          initial_home_store_id: input.homeStore,
                          initial_start_date: input.startDate,
                        },
                      }),
                    )
                  ).id;
                }
                changed();
              }
              if (!p.staffId) throw new Error("スタッフを指定してください。");
              if (!p.linked) {
                await result(
                  api.POST(
                    "/corporates/{corporate_id}/staffs/{staff_id}/person-link",
                    {
                      params: {
                        path: {
                          corporate_id: corporateId,
                          staff_id: p.staffId,
                        },
                      },
                      body: { person_id: personId },
                    },
                  ),
                );
                p.linked = true;
                changed();
              }
            },
      invite: (personId) =>
        result(
          api.POST("/corporates/{corporate_id}/user-invitations", {
            params,
            body: {
              person_id: personId,
              addressee: input.addressee,
              role,
              expires_at: input.expiresAt,
              store_ids: storeIds,
              staff_id: role === "corporate_admin" ? null : p.staffId,
            },
          }),
        ),
    },
    changed,
  );
  return prepared;
}

export const invitationStatus = (corporateId: string, invitationId: string) =>
  result(
    api.GET("/corporates/{corporate_id}/user-invitations/{invitation_id}", {
      params: {
        path: { corporate_id: corporateId, invitation_id: invitationId },
      },
    }),
  );
