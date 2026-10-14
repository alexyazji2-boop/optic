"""Does a wide or rising VIXEQ - VIX gap come before market stress?

Daily, 2014-06-19 to 2026-10-13 (Cboe CSVs). Outcomes over the next 21 and
63 sessions: the S&P 500's maximum drawdown from today's close, and the
change in VIX. Compared by quintile of the gap (level, and its 21-day change),
with the quintiles cut on data up to each day only (expanding), so no
look-ahead in the bucketing. Overlapping windows: the counts overstate the
independent evidence about 21x/63x; read the spreads, not the t-stats.
"""
import os, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
H = os.path.dirname(os.path.abspath(__file__))
def cb(name, col):
    d = pd.read_csv(os.path.join(H, "cboe", name + ".csv")); d["DATE"] = pd.to_datetime(d["DATE"])
    return d.set_index("DATE")[col].astype(float).rename(name)
vix, vixeq, dspx, cor = cb("VIX", "CLOSE"), cb("VIXEQ", "VIXEQ"), cb("DSPX", "DSPX"), cb("COR1M", "CLOSE")
spx = yf.Ticker("^GSPC").history(period="max")["Close"]; spx.index = spx.index.tz_localize(None).normalize(); spx = spx.rename("spx")
df = pd.concat([vix, vixeq, dspx, cor, spx], axis=1, join="inner").dropna()
df["gap"] = df.VIXEQ - df.VIX
df["gap_chg21"] = df.gap - df.gap.shift(21)
c = df.spx.to_numpy()
for h in (21, 63):
    dd = np.full(len(c), np.nan); vchg = np.full(len(c), np.nan)
    for i in range(len(c) - h):
        dd[i] = (c[i + 1:i + h + 1].min() / c[i] - 1) * 100
        vchg[i] = df.VIX.iloc[i + h] - df.VIX.iloc[i]
    df["dd%d" % h] = dd; df["dvix%d" % h] = vchg
def expanding_q(s, min_n=504):
    out = pd.Series(np.nan, index=s.index)
    vals = s.to_numpy()
    for i in range(min_n, len(vals)):
        if np.isnan(vals[i]): continue
        hist = vals[:i + 1]; hist = hist[~np.isnan(hist)]
        out.iloc[i] = min(4, int((hist < vals[i]).mean() * 5))
    return out
res = {}
for feat in ("gap", "gap_chg21", "COR1M", "DSPX"):
    q = expanding_q(df[feat])
    t = df.assign(q=q).dropna(subset=["q", "dd63"])
    g = t.groupby("q").agg(n=("dd21", "size"), dd21=("dd21", "mean"), dd63=("dd63", "mean"),
                           dvix21=("dvix21", "mean"), p_dd10_63=("dd63", lambda x: (x < -10).mean() * 100))
    res[feat] = g.round(2)
    print("\n==", feat, "quintile (0 = lowest, expanding cut points)\n", g.round(2).to_string())
# Baseline: plain VIX level quintiles, the thing any gauge has to beat.
q = expanding_q(df["VIX"]); t = df.assign(q=q).dropna(subset=["q", "dd63"])
print("\n== VIX itself\n", t.groupby("q").agg(n=("dd21","size"), dd21=("dd21","mean"), dd63=("dd63","mean"), dvix21=("dvix21","mean"), p_dd10_63=("dd63", lambda x: (x < -10).mean()*100)).round(2).to_string())
# Partial: within VIX terciles, does the gap still sort outcomes?
t = df.dropna(subset=["dd63"]).copy()
t["vix_t"] = pd.qcut(t.VIX, 3, labels=False); t["gap_t"] = pd.qcut(t.gap, 3, labels=False)
print("\n== mean 63-day drawdown by VIX tercile (rows) x gap tercile (cols), full-sample cuts\n", t.pivot_table(index="vix_t", columns="gap_t", values="dd63", aggfunc="mean").round(2).to_string())
print("\nnow:", df.index[-1].date(), "gap %.1f, pct-rank %.0f%%; COR1M %.2f pct-rank %.0f%%; DSPX %.1f pct %.0f%%" % (
    df.gap.iloc[-1], (df.gap < df.gap.iloc[-1]).mean()*100, df.COR1M.iloc[-1], (df.COR1M < df.COR1M.iloc[-1]).mean()*100, df.DSPX.iloc[-1], (df.DSPX < df.DSPX.iloc[-1]).mean()*100))
