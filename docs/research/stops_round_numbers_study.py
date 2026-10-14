"""Do stocks overshoot round numbers differently from other levels?

For each symbol (cached 5m bars, 60 sessions) and each level L on a grid,
find every downward cross: a bar whose low goes below L after the previous
bar's low was at or above it. Then measure the overshoot: how far below L the
low goes (in units of daily ATR(14)) before the first 5m close back above L,
capped at the session's end. A level whose crossings tend to stop a little
past it and come back is where a buffered stop helps.

Round levels: multiples of `step` (10 for >$100, 5 for $20-100, 1 below), and
the control: the same grid shifted by 0.37 * step, i.e. arbitrary prices with
the same spacing. Upward crosses (shorts' stops) are measured the same way.
"""
import glob, os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.expanduser("~/Optic/work/orb-2026-10-14/bars")

def step_for(p):
    return 10.0 if p >= 100 else 5.0 if p >= 20 else 1.0

def daily_atr(df):
    d = df.groupby(df.index.date).agg(h=("High", "max"), l=("Low", "min"), c=("Close", "last"))
    pc = d["c"].shift(1)
    tr = np.maximum(d["h"] - d["l"], np.maximum((d["h"] - pc).abs(), (d["l"] - pc).abs()))
    return tr.rolling(14, min_periods=5).mean().shift(1)   # known before the day

def overshoots(df, offset_frac, direction):
    out = []
    atr = daily_atr(df)
    for day, g in df.groupby(df.index.date):
        a = atr.get(day)
        if a is None or not np.isfinite(a) or a <= 0:
            continue
        lo, hi, cl = g["Low"].to_numpy(), g["High"].to_numpy(), g["Close"].to_numpy()
        step = step_for(cl[0])
        base = np.floor((lo.min() - step) / step) * step + offset_frac * step
        levels = np.arange(base, hi.max() + step, step)
        for L in levels:
            for i in range(1, len(cl)):
                if direction == "down":
                    crossed = lo[i] < L <= lo[i - 1]
                else:
                    crossed = hi[i] > L >= hi[i - 1]
                if not crossed:
                    continue
                ext = 0.0
                back = False
                for k in range(i, len(cl)):
                    ext = max(ext, (L - lo[k]) if direction == "down" else (hi[k] - L))
                    if (cl[k] > L) if direction == "down" else (cl[k] < L):
                        back = True
                        break
                out.append((ext / a, back))
                break   # first cross of this level this session
    return out

res = {}
for path in sorted(glob.glob(os.path.join(BARS, "*.csv"))):
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    m = df.index.hour * 60 + df.index.minute
    df = df[(m >= 570) & (m < 960)]
    for kind, off in (("round", 0.0), ("control", 0.37)):
        for d in ("down", "up"):
            res.setdefault((kind, d), []).extend(overshoots(df, off, d))

summary = {}
for (kind, d), rows in sorted(res.items()):
    e = np.array([r[0] for r in rows]); b = np.array([r[1] for r in rows])
    rec = {"crosses": len(rows), "came_back_same_session_pct": round(b.mean() * 100, 1)}
    for buf in (0.05, 0.1, 0.15, 0.25, 0.5):
        rec["P(overshoot>%.2f ATR)" % buf] = round((e > buf).mean() * 100, 1)
    # Among crosses that came back: how far they went first.
    eb = e[b]
    rec["median_overshoot_if_back_ATR"] = round(float(np.median(eb)), 3) if len(eb) else None
    rec["p80_overshoot_if_back_ATR"] = round(float(np.percentile(eb, 80)), 3) if len(eb) else None
    summary["%s/%s" % (kind, d)] = rec
print(json.dumps(summary, indent=1))
json.dump(summary, open(os.path.join(HERE, "sweeps.json"), "w"), indent=1)
