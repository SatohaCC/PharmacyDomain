import { createFileRoute, Outlet } from "@tanstack/react-router";
export const Route = createFileRoute("/admin/corporates/$corporateId/users")({
  component: Outlet,
});
