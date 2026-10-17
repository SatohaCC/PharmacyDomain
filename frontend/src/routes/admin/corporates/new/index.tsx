import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { CorporateRegistrationPage } from "../../../../features/corporates/ui/corporates-registration-page";
export const Route = createFileRoute("/admin/corporates/new/")({
  beforeLoad: ({ context }) => {
    if (!context.actor.roles.includes("vendor_system_admin"))
      throw new Error("法人を登録する権限がありません。");
  },
  component: NewCorporate,
});

function NewCorporate() {
  const navigate = useNavigate();
  return (
    <CorporateRegistrationPage
      onComplete={(id) =>
        navigate({
          to: "/admin/corporates/$corporateId",
          params: { corporateId: id },
        })
      }
    />
  );
}
