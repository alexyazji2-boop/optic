#!/usr/bin/env node
// Hunt dead frames: a frame is dead if nothing on screen moved since the previous one.
// node dead_frames.mjs [video.json] [--max-delta 3]
// Diffs consecutive PNGs with ffmpeg; writes critique/dead_frames.json and prints a per-scene report.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const src = argv.find((a, i) => !a.startsWith("--") && argv[i - 1] !== "--max-delta") || "video.json";
const mi = argv.indexOf("--max-delta");
const maxDelta = mi >= 0 ? Number(argv[mi + 1]) : 3; // brightest changed pixel (0-255) still counted as "no change"

const dir = path.dirname(path.resolve(src));
const { VIDEO, SCENES } = JSON.parse(fs.readFileSync(src, "utf8"));
const scenes = SCENES.length ? SCENES : [{ name: "all", start: 0, end: VIDEO.frames - 1 }];
const maxRun = Math.max(3, Math.round(0.3 * VIDEO.fps)); // a still held longer than ~0.3s reads as dead

const out = execFileSync(
  "ffmpeg",
  ["-v", "error", "-framerate", String(VIDEO.fps), "-i", path.join(dir, "frames", "f_%04d.png"),
   "-vf", "format=gray,tblend=all_mode=difference,signalstats,metadata=print:file=-", "-f", "null", "-"],
  { maxBuffer: 1 << 28 }
).toString();

// tblend output k is |frame k+1 - frame k|, so it describes motion INTO frame k+1.
const delta = [{ avg: Infinity, max: 255 }];
let cur = null;
for (const line of out.split("\n")) {
  if (line.startsWith("frame:")) delta.push((cur = { avg: 0, max: 0 }));
  const m = line.match(/lavfi\.signalstats\.(YAVG|YMAX)=([\d.e+-]+)/);
  if (m && cur) cur[m[1] === "YAVG" ? "avg" : "max"] = Number(m[2]);
}
if (delta.length !== VIDEO.frames) console.warn(`warning: ${delta.length} frames on disk, VIDEO.frames is ${VIDEO.frames}`);

const BARS = " ▁▂▃▄▅▆▇█";
const report = scenes.map((s) => {
  const dead = [];
  for (let f = s.start + 1; f <= s.end && f < delta.length; f++) if (delta[f].max <= maxDelta) dead.push(f);
  const runs = [];
  for (const f of dead) {
    const last = runs[runs.length - 1];
    if (last && last[1] === f - 1) last[1] = f;
    else runs.push([f, f]);
  }
  const longest = runs.reduce((m, [a, b]) => Math.max(m, b - a + 1), 0);
  const avgs = [];
  for (let f = s.start + 1; f <= s.end && f < delta.length; f++) avgs.push(delta[f].avg);
  const top = Math.max(...avgs, 1e-9);
  const step = Math.max(1, Math.ceil(avgs.length / 48));
  let curve = "";
  for (let i = 0; i < avgs.length; i += step) {
    const v = Math.max(...avgs.slice(i, i + step));
    curve += v === 0 ? "·" : BARS[Math.max(1, Math.round(Math.sqrt(v / top) * 8))];
  }
  return {
    name: s.name, start: s.start, end: s.end,
    dead: dead.length, longestDeadRun: longest,
    deadRuns: runs.map(([a, b]) => `f${a - s.start}-f${b - s.start} (abs ${a}-${b})`),
    motion: longest > maxRun ? "FAIL" : "pass",
    curve,
  };
});

fs.mkdirSync(path.join(dir, "critique"), { recursive: true });
fs.writeFileSync(path.join(dir, "critique", "dead_frames.json"), JSON.stringify({ maxDelta, maxRun, scenes: report }, null, 2));

console.log(`dead = no pixel changed by more than ${maxDelta}/255; FAIL = a dead run longer than ${maxRun} frames`);
for (const r of report) {
  console.log(`\n${r.motion === "FAIL" ? "✗" : "✓"} ${r.name}  f${r.start}-${r.end}  dead ${r.dead}, longest run ${r.longestDeadRun}`);
  console.log(`  motion |${r.curve}|`);
  if (r.deadRuns.length) console.log(`  dead   ${r.deadRuns.slice(0, 6).join(", ")}${r.deadRuns.length > 6 ? ", …" : ""}`);
}
process.exitCode = report.some((r) => r.motion === "FAIL") ? 1 : 0;
