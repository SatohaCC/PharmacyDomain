import { createFileRoute, useRouter } from "@tanstack/react-router";
import {
  getPatient,
  getPatientHeading,
  getMedicalProfile,
  changePatientHeading,
} from "../../../../../features/patients/api/patient-api";
import { PatientDetailView } from "../../../../../features/patients/ui/patient-detail-view";

export const Route = createFileRoute(
  "/stores/$storeId/patients/$patientId/",
)({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const today = new Date().toISOString().slice(0, 10);
    const [patient, heading, medicalProfile] = await Promise.all([
      getPatient(corporateId, params.patientId, abortController.signal),
      getPatientHeading(corporateId, params.patientId, abortController.signal).catch(
        () => null,
      ),
      getMedicalProfile(
        corporateId,
        params.patientId,
        today,
        abortController.signal,
      ).catch(() => null),
    ]);

    return { patient, heading, medicalProfile, corporateId };
  },
  component: PatientDetailComponent,
});

function PatientDetailComponent() {
  const { storeId, patientId } = Route.useParams();
  const { patient, heading, medicalProfile, corporateId } =
    Route.useLoaderData();
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
      medicalProfile={medicalProfile}
      storeId={storeId}
      onUpdateHeading={handleUpdateHeading}
    />
  );
}
