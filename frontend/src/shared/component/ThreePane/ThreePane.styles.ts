import * as stylex from "@stylexjs/stylex";

export const styles = stylex.create({
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    width: "100%",
  },
  grid: {
    display: "grid",
    width: "100%",
    gridTemplateColumns: {
      default: "minmax(220px, 0.9fr) minmax(0, 3.2fr) minmax(260px, 1.9fr)",
      "@media (max-width: 1280px)": "1fr",
    },
    gap: "8px",
    alignItems: "start",
  },
  column: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  footer: {
    position: "fixed",
    bottom: "6px",
    left: 0,
    right: 0,
    zIndex: 30,
    display: "flex",
    justifyContent: "center",
    paddingInline: "8px",
    pointerEvents: "none",
  },
});
