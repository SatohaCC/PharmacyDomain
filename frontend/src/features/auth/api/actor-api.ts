import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
export const currentActor = () => result(api.GET("/me"));
