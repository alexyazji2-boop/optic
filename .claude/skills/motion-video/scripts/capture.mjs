#!/usr/bin/env node
// Screenshot a real page into assets/ so scenes show the actual product, not a mock.
// node capture.mjs <url> <out.png> [--width 1600] [--height 1000] [--scale 2] [--wait 4000]
//                                   [--theme charcoal] [--hide ".selector,.other"]
//                                   [--storage '{"optic.theme":"dark"}'] [--until-gone "Loading"]
import fs from "node:fs";
import path from "node:path";
import { launch } from "./pw.mjs";

const argv = process.argv.slice(2);
const VALUE_OPTS = ["--width", "--height", "--scale", "--wait", "--theme", "--hide", "--storage", "--until-gone"];
const pos = argv.filter((a, i) => !a.startsWith("--") && !VALUE_OPTS.includes(argv[i - 1]));
const opt = (n, d) => (argv.includes(`--${n}`) ? argv[argv.indexOf(`--${n}`) + 1] : d);
const [url, out] = pos;
if (!url || !out) {
  console.error("usage: node capture.mjs <url> <out.png> [--width W] [--height H] [--scale S] [--wait ms] [--theme name] [--hide css]");
  process.exit(2);
}

const browser = await launch();
const page = await browser.newPage({
  viewport: { width: Number(opt("width", 1600)), height: Number(opt("height", 1000)) },
  deviceScaleFactor: Number(opt("scale", 2)),
  reducedMotion: "reduce",
});
const theme = opt("theme", null);
if (theme) await page.addInitScript((t) => document.documentElement.setAttribute("data-theme", t), theme);
// localStorage set before the app boots, for apps that read their theme or settings from it.
const storage = opt("storage", null);
if (storage) await page.addInitScript((kv) => { for (const [k, v] of Object.entries(JSON.parse(kv))) localStorage.setItem(k, v); }, storage);
await page.goto(url, { waitUntil: "networkidle" }).catch(() => {});
const gone = opt("until-gone", null);
if (gone) await page.waitForFunction((t) => !document.body.innerText.includes(t), gone, { timeout: 120000 }).catch(() => console.warn(`"${gone}" still on the page after 120s`));
await page.waitForTimeout(Number(opt("wait", 4000)));
const hide = opt("hide", null);
if (hide) await page.addStyleTag({ content: `${hide} { visibility: hidden !important; }` });
fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
await page.screenshot({ path: out });
console.log(`wrote ${out} from ${url} at ${await page.title()}`);
await browser.close();
