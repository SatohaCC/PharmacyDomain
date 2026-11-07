import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/stores/$storeId/")({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/stores/$storeId/patients",
      params: { storeId: params.storeId },
    });
  },
});
