import { createFileRoute, useRouter } from "@tanstack/react-router";
import {
  getPatient,
  getPatientHeading,
  getMedicalProfile,
  changePatientHeading,
} from "../../../../../features/patients/api/patient-api";
import { PatientDetailView } from "../../../../../features/patients/ui/patient-detail-view";
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
      getPatient(corporateId, params.patientId, abortController.signal),
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
