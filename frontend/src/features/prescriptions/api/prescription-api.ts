import { api } from "../../../shared/api/client";
import { result } from "../../../shared/api/errors";
import type { components } from "../../../shared/api/generated/schema";
import type { RegisterPrescriptionBody } from "../model/prescription";

export type PrescriptionDto = components["schemas"]["PrescriptionDto"];
export type CareEventDto = components["schemas"]["EventDto"];
export type MedicationHistoryDto =
  components["schemas"]["MedicationHistoryDto"];
export type DrugInteractionAuditReportDto =
  components["schemas"]["DrugInteractionAuditReportDto"];

export const getPrescription = (
  corporateId: string,
  prescriptionId: string,
  signal?: AbortSignal,
): Promise<PrescriptionDto> =>
  result(
    api.GET("/corporates/{corporate_id}/prescriptions/{prescription_id}", {
      params: {
        path: { corporate_id: corporateId, prescription_id: prescriptionId },
      },
      signal,
    }),
  );

export const auditPrescriptionInteractions = (
  corporateId: string,
  yjCodes: string[],
  signal?: AbortSignal,
): Promise<DrugInteractionAuditReportDto> =>
  result(
    api.POST(
      "/corporates/{corporate_id}/prescriptions/audit-interactions",
      {
        params: {
          path: { corporate_id: corporateId },
        },
        body: { yj_codes: yjCodes },
        signal,
      },
    ),
  );

export const listPatientCareEvents = (
  corporateId: string,
  storeId: string,
  patientId?: string,
  signal?: AbortSignal,
): Promise<CareEventDto[]> =>
  result(
    api.GET("/corporates/{corporate_id}/stores/{store_id}/care-events", {
      params: {
        path: { corporate_id: corporateId, store_id: storeId },
        query: patientId ? { patient_id: patientId } : {},
      },
      signal,
    }),
  );

export const registerPrescription = (
  corporateId: string,
  body: RegisterPrescriptionBody,
  signal?: AbortSignal,
): Promise<PrescriptionDto> =>
  result(
    api.POST("/corporates/{corporate_id}/prescriptions", {
      params: { path: { corporate_id: corporateId } },
      body,
      signal,
    }),
  );

export const createDispensingEvent = (
  corporateId: string,
  input: {
    store_id: string;
    patient_id: string;
    occurred_at: string;
    prescription_id: string;
  },
  signal?: AbortSignal,
): Promise<CareEventDto> =>
  result(
    api.POST("/corporates/{corporate_id}/events", {
      params: { path: { corporate_id: corporateId } },
      body: {
        store_id: input.store_id,
        patient_id: input.patient_id,
        standard_code: "dispensing",
        occurred_at: input.occurred_at,
        prescription_id: input.prescription_id,
      },
      signal,
    }),
  );

export const startEventMedicationHistory = (
  corporateId: string,
  eventId: string,
  counseledAt: string,
  signal?: AbortSignal,
): Promise<MedicationHistoryDto> =>
  result(
    api.POST(
      "/corporates/{corporate_id}/events/{event_id}/medication-history",
      {
        params: {
          path: { corporate_id: corporateId, event_id: eventId },
        },
        body: {
          method: "face_to_face",
          soap: {
            subjective: [],
            objective: [],
            assessment: [],
            plan: [],
          },
          counseled_at: counseledAt,
          additional_notes: [],
        },
        signal,
      },
    ),
  );
