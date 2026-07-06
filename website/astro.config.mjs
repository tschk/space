import { defineConfig } from "astro/config";
import UnoCSS from "unocss/astro";

export default defineConfig({
  output: "static",
  site: "https://space.tsc.hk",
  integrations: [UnoCSS()],
});