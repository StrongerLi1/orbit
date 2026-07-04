import { build } from "esbuild";
import { cp, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const playcaptchaRoot = dirname(dirname(fileURLToPath(await import.meta.resolve("playcaptcha"))));
const outDir = join(root, "public", "playcaptcha");

await mkdir(outDir, { recursive: true });
await mkdir(join(outDir, "assets"), { recursive: true });

await build({
  entryPoints: [join(root, "scripts", "playcaptcha-island.jsx")],
  bundle: true,
  outfile: join(outDir, "playcaptcha-island.js"),
  format: "iife",
  target: "es2020",
  minify: true,
  sourcemap: false,
});

await cp(join(playcaptchaRoot, "dist", "clawcaptcha.css"), join(outDir, "clawcaptcha.css"));
await cp(join(playcaptchaRoot, "assets", "toys"), join(outDir, "assets", "toys"), { recursive: true });
await cp(join(playcaptchaRoot, "assets", "playcaptcha.svg"), join(root, "public", "playcaptcha.svg"));
