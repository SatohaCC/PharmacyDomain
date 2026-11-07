import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { registerPatient } from "../../../../features/patients/api/patient-api";
import { PatientRegistrationView } from "../../../../features/patients/ui/patient-registration-view";
import type { RegisterPatientInput } from "../../../../features/patients/model/patient";

export const Route = createFileRoute("/stores/$storeId/patients/new")({
  component: NewPatientComponent,
});

function NewPatientComponent() {
  const { storeId } = Route.useParams();
  const { actor } = Route.useRouteContext();
  const navigate = useNavigate();

  const handleSubmit = async (input: RegisterPatientInput) => {
    if (!actor.corporate_id) {
      throw new Error("所属法人が設定されていません。");
    }
    const newId = await registerPatient(actor.corporate_id, input);
    await navigate({
      to: "/stores/$storeId/patients/$patientId",
      params: { storeId, patientId: newId },
    });
  };

  return <PatientRegistrationView storeId={storeId} onSubmit={handleSubmit} />;
}
