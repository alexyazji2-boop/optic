#!/usr/bin/env node
// Headless render loop: paint each frame in Chromium, screenshot it, stitch with ffmpeg.
// node render.mjs scene.html [--from N] [--to N] [--scale 0.5] [--workers 4]
//                            [--no-audio] [--no-video] [--allow-css]
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { renderAudio } from "./audio.mjs";
import { launch } from "./pw.mjs";

const argv = process.argv.slice(2);
const flag = (name) => argv.includes(`--${name}`);
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const VALUE_OPTS = ["--from", "--to", "--scale", "--workers"];
const page = argv.find((a, i) => !a.startsWith("--") && !VALUE_OPTS.includes(argv[i - 1]));
if (!page) {
  console.error("usage: node render.mjs scene.html [--from N] [--to N] [--scale S] [--workers N] [--no-audio] [--no-video]");
  process.exit(2);
}

const pageUrl = pathToFileURL(path.resolve(page)).href;
const outDir = path.dirname(path.resolve(page));
const framesDir = path.join(outDir, "frames");
fs.mkdirSync(framesDir, { recursive: true });
const framePath = (f) => path.join(framesDir, `f_${String(f).padStart(4, "0")}.png`);

const browser = await launch();
const scale = Number(opt("scale", 1));

async function openPage() {
  const probe = await browser.newPage();
  await probe.goto(pageUrl);
  const video = await probe.evaluate(() => window.VIDEO);
  await probe.close();
  const p = await browser.newPage({ viewport: { width: video.width, height: video.height }, deviceScaleFactor: scale });
  await p.goto(pageUrl);
  await p.evaluate(async () => {
    await document.fonts.ready;
    if (window.ready) await window.ready;
  });
  return p;
}

const first = await openPage();
const meta = await first.evaluate(() => ({ VIDEO: window.VIDEO, SCENES: window.SCENES || [], CUES: window.CUES || [] }));
const { VIDEO } = meta;
fs.writeFileSync(path.join(outDir, "video.json"), JSON.stringify(meta, null, 2));

// Ban basic CSS motion: transitions and keyframe animations make frames depend on wall-clock time.
await first.evaluate((f) => window.renderFrame(f), 0);
const cssMotion = await first.evaluate(() =>
  [...document.querySelectorAll("*")]
    .filter((el) => {
      const s = getComputedStyle(el);
      return s.transitionDuration.split(",").some((d) => parseFloat(d) > 0) || s.animationName !== "none";
    })
    .slice(0, 10)
    .map((el) => el.tagName.toLowerCase() + (el.id ? `#${el.id}` : "") + (el.className && typeof el.className === "string" ? `.${el.className.split(" ").join(".")}` : ""))
);
if (cssMotion.length && !flag("allow-css")) {
  console.error(`CSS transition/animation found on: ${cssMotion.join(", ")}\nDrive all motion from renderFrame with springs (or pass --allow-css).`);
  await browser.close();
  process.exit(1);
}

const from = Number(opt("from", 0));
const to = Math.min(Number(opt("to", VIDEO.frames - 1)), VIDEO.frames - 1);
const workers = Math.max(1, Number(opt("workers", 1)));

if (!flag("no-video")) {
  const t0 = Date.now();
  const pages = [first];
  for (let i = 1; i < workers; i++) pages.push(await openPage());
  let next = from;
  let done = 0;
  await Promise.all(
    pages.map(async (p) => {
      while (next <= to) {
        const f = next++;
        await p.evaluate((n) => window.renderFrame(n), f);
        await p.screenshot({ path: framePath(f), caret: "hide" });
        if (++done % 30 === 0) process.stdout.write(`\rframe ${done}/${to - from + 1}`);
      }
    })
  );
  console.log(`\rrendered ${done} frames (${from}-${to}) in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
await browser.close();

let audio = null;
if (!flag("no-audio")) {
  audio = path.join(outDir, "audio.wav");
  renderAudio(meta, audio);
}

const missing = [];
for (let f = 0; f < VIDEO.frames; f++) if (!fs.existsSync(framePath(f))) missing.push(f);
if (missing.length) {
  console.log(`not stitching: ${missing.length} frames missing (first ${missing[0]})`);
} else {
  const out = path.join(outDir, VIDEO.out || "out.mp4");
  const args = ["-y", "-v", "error", "-framerate", String(VIDEO.fps), "-i", path.join(framesDir, "f_%04d.png")];
  if (audio) args.push("-i", audio);
  args.push("-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart");
  if (audio) args.push("-c:a", "aac", "-b:a", "192k", "-shortest");
  args.push(out);
  execFileSync("ffmpeg", args, { stdio: "inherit" });
  console.log(`wrote ${out}`);
}
