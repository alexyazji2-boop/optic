#!/usr/bin/env node
// Synthesize the soundtrack from the page's cue list. No samples, no dependencies.
// node audio.mjs [video.json] [audio.wav]    (render.mjs calls renderAudio directly)
//
// VIDEO.bed: "pulse" (default) kick on beats, hats on 8ths, soft pad | "none"
// CUES: [{ frame, sound: kick|tick|pop|whoosh|riser|bass, gain }]
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SR = 48000;

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (((t ^ (t >>> 14)) >>> 0) / 4294967296) * 2 - 1;
  };
}

// Each voice writes into buf starting at sample `at`. `lead` = seconds the sound starts before its cue.
const VOICES = {
  kick: { lead: 0, play(buf, at, g) {
    let ph = 0;
    for (let i = 0; i < SR * 0.4; i++) {
      const t = i / SR;
      ph += (2 * Math.PI * (45 + 110 * Math.exp(-t * 28))) / SR;
      add(buf, at + i, Math.sin(ph) * Math.exp(-t * 9) * g);
    }
  } },
  bass: { lead: 0, play(buf, at, g) {
    for (let i = 0; i < SR * 0.6; i++) {
      const t = i / SR;
      const env = Math.min(1, t * 200) * Math.exp(-t * 4);
      add(buf, at + i, (Math.sin(2 * Math.PI * 55 * t) + 0.3 * Math.sin(2 * Math.PI * 110 * t)) * env * 0.6 * g);
    }
  } },
  tick: { lead: 0, play(buf, at, g, r) {
    let prev = 0;
    for (let i = 0; i < SR * 0.04; i++) {
      const n = r();
      add(buf, at + i, (n - prev) * 0.5 * Math.exp(-(i / SR) * 120) * g); // differenced noise = bright
      prev = n;
    }
  } },
  pop: { lead: 0, play(buf, at, g) {
    let ph = 0;
    for (let i = 0; i < SR * 0.12; i++) {
      const t = i / SR;
      ph += (2 * Math.PI * (500 + 700 * Math.min(1, t / 0.03))) / SR;
      add(buf, at + i, Math.sin(ph) * Math.exp(-t * 35) * 0.5 * g);
    }
  } },
  whoosh: { lead: 0.35, play(buf, at, g, r) {
    const len = SR * 0.55;
    let lp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / len;
      const cutoff = 0.02 + 0.25 * Math.sin(Math.PI * t); // sweep the filter up and back down
      lp += cutoff * (r() - lp);
      add(buf, at + i, lp * Math.pow(Math.sin(Math.PI * Math.min(1, t * 1.6)), 2) * 1.4 * g);
    }
  } },
  riser: { lead: 1.5, play(buf, at, g, r) {
    const len = SR * 1.5;
    let ph = 0;
    let lp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / len;
      ph += (2 * Math.PI * (180 + 620 * t * t)) / SR;
      lp += (0.01 + 0.2 * t) * (r() - lp);
      add(buf, at + i, (Math.sin(ph) * 0.25 + lp * 0.8) * t * t * g);
    }
  } },
};

function add(buf, i, v) {
  if (i >= 0 && i < buf.length) buf[i] += v;
}

function pad(buf, bpm, r) {
  const chord = [220, 261.63, 329.63, 392]; // A minor 7
  const bar = (4 * 60) / bpm;
  for (let i = 0; i < buf.length; i++) {
    const t = i / SR;
    const swell = 0.5 - 0.5 * Math.cos((2 * Math.PI * t) / (bar * 2));
    let v = 0;
    for (const f of chord) v += Math.sin(2 * Math.PI * f * t + Math.sin(2 * Math.PI * 0.2 * t)) * 0.04;
    buf[i] += v * (0.4 + 0.6 * swell) + r() * 0.002;
  }
}

export function renderAudio({ VIDEO, CUES = [] }, outPath) {
  const seconds = VIDEO.frames / VIDEO.fps;
  const buf = new Float32Array(Math.ceil(seconds * SR));
  const r = rng(VIDEO.seed || 7);
  const beatSec = 60 / VIDEO.bpm;
  const cues = [...CUES];

  if ((VIDEO.bed || "pulse") === "pulse") {
    pad(buf, VIDEO.bpm, r);
    for (let b = 0; b * beatSec < seconds; b++) {
      cues.push({ seconds: b * beatSec, sound: "kick", gain: 0.55, bed: true });
      cues.push({ seconds: (b + 0.5) * beatSec, sound: "tick", gain: 0.25, bed: true });
    }
  }

  let worst = 0;
  for (const c of cues) {
    const voice = VOICES[c.sound];
    if (!voice) throw new Error(`unknown sound "${c.sound}" (have ${Object.keys(VOICES).join(", ")})`);
    const sec = c.seconds ?? c.frame / VIDEO.fps;
    if (!c.bed) {
      const off = Math.abs(sec / (beatSec / 2) - Math.round(sec / (beatSec / 2))) * (beatSec / 2) * 1000;
      worst = Math.max(worst, off);
    }
    voice.play(buf, Math.round((sec - voice.lead) * SR), c.gain ?? 1, r);
  }

  let peak = 0;
  for (let i = 0; i < buf.length; i++) {
    buf[i] = Math.tanh(buf[i] * 1.2);
    peak = Math.max(peak, Math.abs(buf[i]));
  }
  const norm = peak > 0 ? 0.89 / peak : 1; // about -1 dBFS
  const fade = Math.round(SR * 0.05);
  const pcm = Buffer.alloc(44 + buf.length * 2);
  pcm.write("RIFF", 0); pcm.writeUInt32LE(36 + buf.length * 2, 4); pcm.write("WAVE", 8);
  pcm.write("fmt ", 12); pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(1, 22);
  pcm.writeUInt32LE(SR, 24); pcm.writeUInt32LE(SR * 2, 28); pcm.writeUInt16LE(2, 32); pcm.writeUInt16LE(16, 34);
  pcm.write("data", 36); pcm.writeUInt32LE(buf.length * 2, 40);
  for (let i = 0; i < buf.length; i++) {
    const edge = Math.min(1, i / fade, (buf.length - 1 - i) / fade);
    pcm.writeInt16LE(Math.round(Math.max(-1, Math.min(1, buf[i] * norm * edge)) * 32767), 44 + i * 2);
  }
  fs.writeFileSync(outPath, pcm);
  console.log(`wrote ${outPath}: ${seconds.toFixed(2)}s, ${VIDEO.bpm} BPM, ${CUES.length} cues, worst off-beat ${worst.toFixed(0)} ms (8th-note grid)`);
  return worst;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const src = process.argv[2] || "video.json";
  const out = process.argv[3] || path.join(path.dirname(src), "audio.wav");
  renderAudio(JSON.parse(fs.readFileSync(src, "utf8")), out);
}
