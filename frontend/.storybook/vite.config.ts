import { defineConfig } from "vite";
import stylex from "@stylexjs/unplugin";
export default defineConfig({ plugins: [stylex.vite({ useCSSLayers: true })] });
