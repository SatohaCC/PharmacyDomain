import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type {
  ChangePatientHeadingInput,
  PatientDetail,
  PatientHeading,
  PatientMedicalProfile,
  PatientSummary,
  RegisterPatientInput,
} from "../model/patient";

export const listPatients = (
  corporateId: string,
  keyword?: string,
  signal?: AbortSignal,
): Promise<PatientSummary[]> =>
  result(
    api.GET("/corporates/{corporate_id}/patients", {
      params: {
        path: { corporate_id: corporateId },
        query: { keyword: keyword || undefined },
      },
      signal,
    }),
  );

export const getPatient = (
  corporateId: string,
  patientId: string,
  signal?: AbortSignal,
): Promise<PatientDetail> =>
  result(
    api.GET("/corporates/{corporate_id}/patients/{patient_id}", {
      params: {
        path: { corporate_id: corporateId, patient_id: patientId },
      },
      signal,
    }),
  );

export const registerPatient = async (
  corporateId: string,
  body: RegisterPatientInput,
): Promise<string> => {
  const res = await result(
    api.POST("/corporates/{corporate_id}/patients", {
      params: { path: { corporate_id: corporateId } },
      body: {
        ...body,
        birth_date: body.birth_date || null,
      },
    }),
  );
  return res.id;
};

export const getPatientHeading = (
  corporateId: string,
  patientId: string,
  signal?: AbortSignal,
): Promise<PatientHeading> =>
  result(
    api.GET("/corporates/{corporate_id}/patients/{patient_id}/heading", {
      params: {
        path: { corporate_id: corporateId, patient_id: patientId },
      },
      signal,
    }),
  );

export const changePatientHeading = (
  corporateId: string,
  patientId: string,
  body: ChangePatientHeadingInput,
): Promise<PatientHeading> =>
  result(
    api.PATCH("/corporates/{corporate_id}/patients/{patient_id}/heading", {
      params: {
        path: { corporate_id: corporateId, patient_id: patientId },
      },
      body,
    }),
  );

export const getMedicalProfile = (
  corporateId: string,
  patientId: string,
  asOf: string,
  signal?: AbortSignal,
): Promise<PatientMedicalProfile> =>
  result(
    api.GET("/corporates/{corporate_id}/patients/{patient_id}/medical-profile", {
      params: {
        path: { corporate_id: corporateId, patient_id: patientId },
        query: { as_of: asOf },
      },
      signal,
    }),
  );
