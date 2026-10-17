import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { router } from "./app/router";
import "./style.css";
import { configureApplication } from "./app/composition";
configureApplication();
createRoot(document.getElementById("root")!).render(
  <RouterProvider router={router} />,
);
