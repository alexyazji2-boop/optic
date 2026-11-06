#!/usr/bin/env node
// One contact sheet per scene so Claude can watch its own frames and grade them.
// node contact_sheet.mjs [video.json] [--every 3] [--cols 6] [--tile 320]
// Writes sheets/<nn>-<scene>_<page>.jpg, tiles left to right, top to bottom, labelled with the frame number.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const argv = process.argv.slice(2);
const VALUE_OPTS = ["--every", "--cols", "--tile"];
const opt = (n, d) => (argv.includes(`--${n}`) ? Number(argv[argv.indexOf(`--${n}`) + 1]) : d);
const src = argv.find((a, i) => !a.startsWith("--") && !VALUE_OPTS.includes(argv[i - 1])) || "video.json";
const every = opt("every", 3);
const cols = opt("cols", 6);
const tile = opt("tile", 320);

const dir = path.dirname(path.resolve(src));
const { VIDEO, SCENES } = JSON.parse(fs.readFileSync(src, "utf8"));
const scenes = SCENES.length ? SCENES : [{ name: "all", start: 0, end: VIDEO.frames - 1 }];
const sheets = path.join(dir, "sheets");
fs.rmSync(sheets, { recursive: true, force: true });
fs.mkdirSync(sheets);

const font = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"].find(fs.existsSync);
const hasDrawtext = execFileSync("ffmpeg", ["-hide_banner", "-filters"]).toString().includes(" drawtext ");

scenes.forEach((s, idx) => {
  const count = s.end - s.start + 1;
  const tiles = Math.ceil(count / every);
  const rows = Math.min(6, Math.ceil(tiles / cols));
  const label = hasDrawtext && font
    ? `,drawtext=fontfile=${font}:text='f%{eif\\:n*${every}+${s.start}\\:d}':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4`
    : "";
  const name = `${String(idx + 1).padStart(2, "0")}-${s.name.replace(/[^\w-]+/g, "_")}`;
  execFileSync("ffmpeg", [
    "-v", "error", "-y", "-start_number", String(s.start), "-i", path.join(dir, "frames", "f_%04d.png"),
    "-vf", `select='lt(n\\,${count})*not(mod(n\\,${every}))',setpts=N/TB,scale=${tile}:-2${label},tile=${cols}x${rows}:padding=4:color=gray`,
    "-fps_mode", "passthrough", "-q:v", "3", path.join(sheets, `${name}_%02d.jpg`),
  ]);
});
console.log(`wrote ${fs.readdirSync(sheets).length} sheets to ${sheets} (every ${every} frames${hasDrawtext && font ? ", labelled" : ""})`);
