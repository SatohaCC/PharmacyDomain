import { useRef, useState } from "react";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { registerPatient } from "../../../../features/patients/api/patient-api";
import { PatientRegistrationView } from "../../../../features/patients/components/PatientRegistrationView";
import type { RegisterPatientInput } from "../../../../features/patients/model/patient";

export const Route = createFileRoute("/stores/$storeId/patients/new")({
  beforeLoad: ({ params, context }) => {
    const roles = context.actor.roles ?? [];
    const canManage =
      roles.includes("corporate_admin") ||
      roles.includes("vendor_system_admin");
    if (!canManage) {
      throw redirect({
        to: "/stores/$storeId/patients",
        params: { storeId: params.storeId },
      });
    }
  },
  component: NewPatientComponent,
});

function NewPatientComponent() {
  const { storeId } = Route.useParams();
  const { actor } = Route.useRouteContext();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const lock = useRef(false);

  const handleSubmit = async (input: RegisterPatientInput) => {
    if (submitting || lock.current) return;
    if (!actor.corporate_id) {
      throw new Error("所属法人が設定されていません。");
    }
    lock.current = true;
    setSubmitting(true);
    try {
      const newId = await registerPatient(actor.corporate_id, input);
      await navigate({
        to: "/stores/$storeId/patients/$patientId",
        params: { storeId, patientId: newId },
      });
    } finally {
      lock.current = false;
      setSubmitting(false);
    }
  };

  return (
    <PatientRegistrationView
      storeId={storeId}
      onSubmit={handleSubmit}
      isSubmitting={submitting}
    />
  );
}
