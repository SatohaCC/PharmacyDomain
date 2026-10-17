import { createFileRoute, redirect } from "@tanstack/react-router";
export const Route = createFileRoute("/admin/")({
  beforeLoad: ({ context }) => {
    if (context.actor.roles.includes("vendor_system_admin"))
      throw redirect({ to: "/admin/corporates" });
    if (context.actor.corporate_id)
      throw redirect({
        to: "/admin/corporates/$corporateId",
        params: { corporateId: context.actor.corporate_id },
      });
  },
});
