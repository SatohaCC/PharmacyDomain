import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

vi.mock("@stylexjs/stylex", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("@stylexjs/stylex");
  return {
    ...actual,
    defineVars: (vars: Record<string, unknown>) => vars,
    create: (styles: Record<string, unknown>) => styles,
    props: () => ({}),
  };
});

afterEach(cleanup);
