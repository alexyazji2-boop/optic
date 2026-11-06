// Find Playwright and a browser to drive, shared by render.mjs and capture.mjs.
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export function loadPlaywright() {
  try {
    return createRequire(path.join(process.cwd(), "noop.js"))("playwright");
  } catch {}
  const npx = path.join(os.homedir(), ".npm", "_npx");
  for (const d of fs.existsSync(npx) ? fs.readdirSync(npx) : []) {
    const p = path.join(npx, d, "node_modules", "playwright");
    if (fs.existsSync(p)) return createRequire(path.join(npx, d, "noop.js"))("playwright");
  }
  console.error("Playwright not found. Run: npm i -D playwright && npx playwright install chromium");
  process.exit(1);
}

// Playwright's bundled headless shell, else the installed Chrome (its bundled build may not be downloaded).
export async function launch() {
  const { chromium } = loadPlaywright();
  try {
    return await chromium.launch();
  } catch (e) {
    try {
      return await chromium.launch({ channel: "chrome" });
    } catch {
      throw e;
    }
  }
}
