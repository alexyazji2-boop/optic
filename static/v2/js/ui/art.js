// The onboarding illustration: a lens iris projecting the S&P 500's real recent
// history onto a screen, the camera obscura behind the name "Optic". Only on
// the welcome; routine research screens carry no decoration. Its colours are
// the charcoal panel's own, which stays dark in both themes.
import { num } from '../core/format.js';

export function art(series) {
  const cx = 168, cy = 262, R = 120, r = 34;
  const hex = [0, 1, 2, 3, 4, 5].map((i) => { const a = Math.PI / 3 * i + Math.PI / 6; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });
  const blades = hex.map((p, i) => {
    const q = hex[(i + 1) % 6];
    const a1 = Math.PI / 3 * i + Math.PI / 6 + 0.9, a2 = Math.PI / 3 * (i + 1) + Math.PI / 6 + 0.9;
    const o1 = [cx + R * Math.cos(a1), cy + R * Math.sin(a1)], o2 = [cx + R * Math.cos(a2), cy + R * Math.sin(a2)];
    return `<path d="M${p[0].toFixed(1)} ${p[1].toFixed(1)} L${q[0].toFixed(1)} ${q[1].toFixed(1)} L${o2[0].toFixed(1)} ${o2[1].toFixed(1)} A${R} ${R} 0 0 0 ${o1[0].toFixed(1)} ${o1[1].toFixed(1)} Z" fill="${i % 2 ? '#2b2824' : '#24221e'}" stroke="rgba(212,177,68,.42)" stroke-width="1"/>`;
  }).join('');
  const ys = (series || []).map((p) => p.c).filter(Number.isFinite);
  const sx0 = 410, sx1 = 598, sy0 = 160, sy1 = 360;
  let line = '', end = '', label = 'A lens iris projecting a line chart onto a screen';
  if (ys.length > 2) {
    const lo = Math.min(...ys), hi = Math.max(...ys), s = hi - lo || 1;
    line = ys.map((v, i) => `${i ? 'L' : 'M'}${(sx0 + i / (ys.length - 1) * (sx1 - sx0)).toFixed(1)} ${(sy1 - (v - lo) / s * (sy1 - sy0)).toFixed(1)}`).join('');
    end = `<circle cx="${sx1}" cy="${(sy1 - (ys[ys.length - 1] - lo) / s * (sy1 - sy0)).toFixed(1)}" r="4" fill="#b0861b"/>`;
    const chg = (ys[ys.length - 1] / ys[0] - 1) * 100;
    label = `A lens iris projecting the S&P 500's last six months, ${chg >= 0 ? 'up' : 'down'} ${num(Math.abs(chg), 1)} percent, onto a screen`;
  }
  return `<svg viewBox="0 0 640 520" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${label}">
    <defs>
      <linearGradient id="art-beam" x1="0" x2="1"><stop offset="0" stop-color="#fbefc4" stop-opacity=".62"/><stop offset=".55" stop-color="#f3dfa0" stop-opacity=".18"/><stop offset="1" stop-color="#f3dfa0" stop-opacity=".06"/></linearGradient>
      <radialGradient id="art-open" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#fff8e1"/><stop offset=".7" stop-color="#f6e2a2"/><stop offset="1" stop-color="#d4b144"/></radialGradient>
      <linearGradient id="art-screen" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f6eedb"/><stop offset="1" stop-color="#e9dec4"/></linearGradient>
      <radialGradient id="art-ring" cx="50%" cy="50%" r="50%"><stop offset=".86" stop-color="#1b1a18" stop-opacity="0"/><stop offset="1" stop-color="#d4b144" stop-opacity=".35"/></radialGradient>
    </defs>
    <path d="M${cx + 20} ${cy - 30} L392 112 L392 412 L${cx + 20} ${cy + 30} Z" fill="url(#art-beam)"/>
    <rect x="392" y="112" width="224" height="300" rx="8" fill="url(#art-screen)"/>
    <rect x="392" y="112" width="224" height="300" rx="8" fill="none" stroke="rgba(27,26,24,.12)"/>
    ${line ? `<path d="${line}" fill="none" stroke="#1b1a18" stroke-width="2.2" stroke-linejoin="round"/>${end}` : ''}
    <circle cx="${cx}" cy="${cy}" r="${R + 14}" fill="url(#art-ring)"/>
    <circle cx="${cx}" cy="${cy}" r="${R + 2}" fill="none" stroke="rgba(212,177,68,.55)" stroke-width="1.5"/>
    <circle cx="${cx}" cy="${cy}" r="${R + 10}" fill="none" stroke="rgba(212,177,68,.18)" stroke-width="1"/>
    <polygon points="${hex.map((p) => p.map((v) => v.toFixed(1)).join(',')).join(' ')}" fill="url(#art-open)"/>
    ${blades}
  </svg>`;
}
