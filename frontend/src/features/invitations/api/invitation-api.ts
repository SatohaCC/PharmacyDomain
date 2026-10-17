import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
export const acceptInvitation = (secret: string) =>
  result(api.POST("/user-invitations/acceptance", { body: { secret } }));
export const acceptedActor = () => result(api.GET("/me"));
