# Scout

Pulse's mascot: concept 03 ("Scout") from the user's snowman concept sheet,
rendered in 3D. The renders the app uses are committed in `static/scout/`;
this folder holds what made them.

`render_scout.py` builds Scout as a signed-distance scene and ray-marches it
in numpy (there is no Blender on the machine and the app has no build step).
His face is the Pulse mark (the ring and heartbeat on the Pulse button) inset
in gold; `SCOUT_FACE=optic` reproduces the earlier two Optic-lens eyes and
smile (commit 2deec49). The render has matte clay grain fixed to each part,
a key light, a fill, a hemisphere sky, soft shadows and ambient occlusion. Every frame shares one camera and one
light rig, so a blink, a turn or a wave changes only the pose. It writes:

| file | contents |
| --- | --- |
| `static/scout/scout-full@3x.webp`, `@2x` | 22 frames, 288x380 (3x) / 192x253 (2x), whole figure |
| `static/scout/scout-compact@3x.webp`, `@2x` | the same 22 poses as a bust, 144x156 / 96x104 |
| `static/scout/scout-full-tail@3x.webp`, `@2x` | the scarf's tail alone, 12 wind phases, same frame size |
| `static/scout/scout-compact-tail@3x.webp`, `@2x` | the same for the bust |
| `static/scout/frames.json` | frame names in order, the wind phase count, and the frame sizes |
| `static/scout/scout.png` | the resting pose at 900x1188, for reference |

The tail is a separate layer drawn under the body, so one flutter loop runs
behind every pose and a raised hand still covers the scarf. It is rendered
with the body held out but still casting shadow, so its lighting matches.

The 2x strips are the 3x renders resampled down (premultiplied Lanczos), never
an enlargement. Each 3x frame is box-filtered from 4x4 (full) or 6x6 (compact)
rays per pixel.

The frame order in `frames.json` is a contract with `FRAME` in
`static/components/scout.js` and with `tests/test_pulse_scout.py`. Add frames
at the end, never in the middle.

Regenerate from the repository root (about 35 minutes on an M2 Pro with 16 GB;
it uses 6 workers and marches rays in chunks, because a whole 3x frame at once
swapped the machine):

```bash
.venv/bin/python optic-brand/scout/render_scout.py
```
