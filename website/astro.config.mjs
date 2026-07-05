import { defineConfig } from "astro/config";
import UnoCSS from "unocss/astro";

export default defineConfig({
  output: "static",
  integrations: [UnoCSS()],
});