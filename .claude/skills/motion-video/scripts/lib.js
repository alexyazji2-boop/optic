// Motion helpers for frame-driven video. Pure functions of time: no clocks, no state.
// Loads as a classic <script> (window.Motion) or with require() in Node.
(function (root) {
  const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
  const lerp = (a, b, p) => a + (b - a) * p;

  // Closed-form damped spring from 0 to 1, t in seconds since release.
  // Same parameters as Framer Motion / react-spring: stiffness, damping, mass, velocity.
  function spring(t, { stiffness = 170, damping = 26, mass = 1, velocity = 0 } = {}) {
    if (t <= 0) return 0;
    const w0 = Math.sqrt(stiffness / mass);
    const zeta = damping / (2 * Math.sqrt(stiffness * mass));
    const y0 = -1; // displacement from the target at release
    const v0 = velocity;
    let y;
    if (zeta < 1) {
      const wd = w0 * Math.sqrt(1 - zeta * zeta);
      y = Math.exp(-zeta * w0 * t) * (y0 * Math.cos(wd * t) + ((v0 + zeta * w0 * y0) / wd) * Math.sin(wd * t));
    } else if (zeta === 1) {
      y = Math.exp(-w0 * t) * (y0 + (v0 + w0 * y0) * t);
    } else {
      const s = Math.sqrt(zeta * zeta - 1);
      const r1 = -w0 * (zeta - s);
      const r2 = -w0 * (zeta + s);
      const a = (v0 - r2 * y0) / (r1 - r2);
      y = a * Math.exp(r1 * t) + (y0 - a) * Math.exp(r2 * t);
    }
    return 1 + y;
  }

  const springTo = (from, to, t, cfg) => lerp(from, to, spring(t, cfg));

  // Seconds a spring takes to stay within `eps` of its target (for planning scene length).
  function settleTime(cfg, eps = 0.002, fps = 240) {
    let last = 0;
    for (let i = 1; i < fps * 10; i++) {
      if (Math.abs(1 - spring(i / fps, cfg)) > eps) last = i;
    }
    return last / fps;
  }

  // Named feels. Lower stiffness for heavier things, lower damping for more overshoot.
  const SPRINGS = {
    snappy: { stiffness: 400, damping: 30 },
    pop: { stiffness: 320, damping: 16 },
    gentle: { stiffness: 120, damping: 20 },
    heavy: { stiffness: 90, damping: 18, mass: 1.6 },
    wobbly: { stiffness: 180, damping: 10 },
  };

  // Beat grid. Cuts and audio hits sit on these frames.
  const beatSeconds = (beat, bpm) => (beat * 60) / bpm;
  const beatFrame = (beat, { bpm, fps }) => Math.round(beatSeconds(beat, bpm) * fps);

  // Scene list from beat lengths: scenes(["intro", 2], ["ui", 4]) with {bpm, fps}.
  function scenes(list, grid) {
    let beat = 0;
    return list.map(([name, beats]) => {
      const s = { name, start: beatFrame(beat, grid), end: beatFrame(beat + beats, grid) - 1, beat };
      beat += beats;
      return s;
    });
  }

  // Seconds since `startFrame`, negative before it. Use as a spring's t.
  const since = (frame, startFrame, fps) => (frame - startFrame) / fps;

  // Deterministic PRNG so particles and jitter are identical on every render.
  function rng(seed = 1) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const Motion = { clamp, lerp, spring, springTo, settleTime, SPRINGS, beatSeconds, beatFrame, scenes, since, rng };
  if (typeof module === "object" && module.exports) module.exports = Motion;
  else root.Motion = Motion;
})(typeof self !== "undefined" ? self : this);
