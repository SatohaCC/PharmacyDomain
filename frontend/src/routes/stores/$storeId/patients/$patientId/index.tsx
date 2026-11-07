import { createFileRoute, useRouter } from "@tanstack/react-router";
import {
  getPatient,
  getPatientHeading,
  getMedicalProfile,
  changePatientHeading,
  listPatients,
} from "../../../../../features/patients/api/patient-api";
import { PatientDetailView } from "../../../../../features/patients/ui/patient-detail-view";
import type { PatientDetail } from "../../../../../features/patients/model/patient";
import { ApiError, errorText } from "../../../../../shared/api/errors";

export const Route = createFileRoute(
  "/stores/$storeId/patients/$patientId/",
)({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const today = new Date().toISOString().slice(0, 10);
    const [patient, headingResult, medicalProfileResult] = await Promise.all([
      getPatient(corporateId, params.patientId, abortController.signal).catch(
        async (err: unknown): Promise<PatientDetail> => {
          if (err instanceof ApiError && err.status === 403) {
            // 店舗ロールは法人台帳への直接アクセス（VIEW_PATIENT）権限を持たないため、
            // 店舗参照契約（listPatients）から患者情報を取得して投影する
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
        },
      ),
      getPatientHeading(corporateId, params.patientId, abortController.signal)
        .then((data) => ({ data, error: null }))
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) {
            return { data: null, error: null };
          }
          return { data: null, error: errorText(err) };
        }),
      getMedicalProfile(
        corporateId,
        params.patientId,
        today,
        abortController.signal,
      )
        .then((data) => ({ data, error: null }))
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) {
            return { data: null, error: null };
          }
          return { data: null, error: errorText(err) };
        }),
    ]);

    return {
      patient,
      heading: headingResult.data,
      headingFetchError: headingResult.error,
      medicalProfile: medicalProfileResult.data,
      medicalProfileFetchError: medicalProfileResult.error,
      corporateId,
    };
  },
  component: PatientDetailComponent,
});

function PatientDetailComponent() {
  const { storeId, patientId } = Route.useParams();
  const {
    patient,
    heading,
    headingFetchError,
    medicalProfile,
    medicalProfileFetchError,
    corporateId,
  } = Route.useLoaderData();
  const router = useRouter();

  const handleUpdateHeading = async (input: {
    expectedRevision: number;
    summary: string | null;
    notes: string | null;
  }) => {
    await changePatientHeading(corporateId, patientId, {
      expected_revision: input.expectedRevision,
      summary: input.summary,
      notes: input.notes,
    });
    await router.invalidate();
  };

  return (
    <PatientDetailView
      patient={patient}
      heading={heading}
      headingFetchError={headingFetchError}
      medicalProfile={medicalProfile}
      medicalProfileFetchError={medicalProfileFetchError}
      storeId={storeId}
      onUpdateHeading={handleUpdateHeading}
    />
  );
}
