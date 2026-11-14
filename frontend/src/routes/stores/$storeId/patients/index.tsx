import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { listPatients } from "../../../../features/patients/api/patient-api";
import { PatientListView } from "../../../../features/patients/components/PatientListView";

export const Route = createFileRoute("/stores/$storeId/patients/")({
  validateSearch: (
    s: Record<string, unknown>,
  ): { keyword?: string } => ({
    keyword: typeof s.keyword === "string" ? s.keyword : undefined,
  }),
  loaderDeps: ({ search }) => search,
  loader: ({ deps, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    return listPatients(corporateId, deps.keyword, abortController.signal);
  },
  component: PatientsIndexComponent,
});

function PatientsIndexComponent() {
  const { storeId } = Route.useParams();
  const search = Route.useSearch();
  const patients = Route.useLoaderData();
  const { actor } = Route.useRouteContext();
  const navigate = useNavigate();

  const canCreatePatient =
    actor.roles?.includes("corporate_admin") ||
    actor.roles?.includes("vendor_system_admin");

  const handleSearch = async (keyword: string) => {
    await navigate({
      to: "/stores/$storeId/patients",
      params: { storeId },
      search: { keyword: keyword || undefined },
    });
  };

  return (
    <PatientListView
      key={search.keyword || ""}
      patients={patients}
      storeId={storeId}
      initialKeyword={search.keyword || ""}
      onSearch={(kw) => void handleSearch(kw)}
      canCreatePatient={canCreatePatient}
    />
  );
}
