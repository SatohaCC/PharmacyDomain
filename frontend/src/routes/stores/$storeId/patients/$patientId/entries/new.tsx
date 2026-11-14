import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { getPatient, listPatients } from "../../../../../../features/patients/api/patient-api";
import type { PatientDetail } from "../../../../../../features/patients/model/patient";
import {
  createDispensingEvent,
  registerPrescription,
  startEventMedicationHistory,
} from "../../../../../../features/prescriptions/api/prescription-api";
import {
  buildRegisterPrescriptionBody,
  type PrescriptionEntryFormInput,
} from "../../../../../../features/prescriptions/model/prescription";
import { EntryRegistrationView } from "../../../../../../features/prescriptions/ui/entry-registration-view";
import { ApiError } from "../../../../../../shared/api/errors";

export const Route = createFileRoute(
  "/stores/$storeId/patients/$patientId/entries/new",
)({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const patient = await getPatient(
      corporateId,
      params.patientId,
      abortController.signal,
    ).catch(async (err: unknown): Promise<PatientDetail> => {
      if (err instanceof ApiError && err.status === 403) {
        const list = await listPatients(
          corporateId,
          undefined,
          abortController.signal,
        );
        const found = list.find((p) => p.id === params.patientId);
        if (found) {
          return {
            id: found.id,
            patient_number: found.patient_number,
            corporate_id: found.corporate_id,
            last_name: found.last_name,
            first_name: found.first_name,
            last_name_kana: found.last_name_kana,
            first_name_kana: found.first_name_kana,
            birth_date: found.birth_date,
            gender: found.gender ?? null,
            postal_code: null,
            address: null,
            phone_number: found.phone_number ?? null,
            status: found.status,
            merged_into_id: null,
            status_history: [],
            profile_history: [],
          };
        }
      }
      throw err;
    });
    return { corporateId, patient };
  },
  component: NewEntryPage,
});

function NewEntryPage() {
  const { storeId, patientId } = Route.useParams();
  const { corporateId, patient } = Route.useLoaderData();
  const navigate = useNavigate();

  const handleSubmit = async (input: PrescriptionEntryFormInput) => {
    const prescription = await registerPrescription(
      corporateId,
      buildRegisterPrescriptionBody(input),
    );
    const nowIso = new Date().toISOString();
    const event = await createDispensingEvent(corporateId, {
      store_id: storeId,
      patient_id: patientId,
      occurred_at: nowIso,
      prescription_id: prescription.id,
    });
    try {
      await startEventMedicationHistory(corporateId, event.event_id, nowIso);
      return { medicationHistoryCreated: true };
    } catch (err: unknown) {
      if (
        err instanceof ApiError &&
        err.status === 403 &&
        err.message.includes("薬剤師資格")
      ) {
        return {
          medicationHistoryCreated: false,
          message:
            "処方箋と受付イベントを登録しました（服薬指導・薬歴開始は薬剤師アカウントで行ってください）。",
        };
      }
      throw err;
    }
  };

  return (
    <EntryRegistrationView
      storeId={storeId}
      patientId={patientId}
      patientName={`${patient.last_name} ${patient.first_name}`}
      onSubmit={handleSubmit}
      onDone={() =>
        void navigate({
          to: "/stores/$storeId/patients/$patientId",
          params: { storeId, patientId },
        })
      }
    />
  );
}
