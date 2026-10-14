"""Are options cheap when IV rank is low? ("buy when IV rank <= 30")

DoltHub daily store (iv = 30-day ATM IV, hv = trailing 30-day realised vol),
every symbol with a full year before the day. For each symbol-day t with 252
prior sessions: IV rank over those 252 sessions; the volatility that followed,
rv_fwd = hv at t + 21 sessions (the 30 calendar days after t). Options are
cheap after the fact when rv_fwd > iv. A delta-hedged long option earns
roughly in proportion to rv_fwd^2 - iv^2, so the variance ratio is reported
too. Buckets of IV rank, pooled; per-symbol-day observations overlap 21x.
"""
import os, sqlite3, sys, json
import numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(H, "store", "dolthub_vol.db"))
df = pd.read_sql("SELECT symbol, day, iv, hv FROM vol WHERE iv IS NOT NULL AND hv IS NOT NULL", con)
df = df.sort_values(["symbol", "day"])
out = []
for sym, g in df.groupby("symbol"):
    if len(g) < 252 + 22: continue
    iv, hv = g.iv.to_numpy(), g.hv.to_numpy()
    for t in range(252, len(g) - 21):
        win = iv[t - 252:t + 1]
        lo, hi = win.min(), win.max()
        if hi <= lo: continue
        out.append((sym, g.day.iloc[t], (iv[t] - lo) / (hi - lo) * 100, iv[t], hv[t + 21], hv[t]))
r = pd.DataFrame(out, columns=["sym", "day", "rank", "iv", "rv_fwd", "hv_now"])
r = r[(r.iv > 0.02) & (r.iv < 3) & (r.rv_fwd > 0.005) & (r.rv_fwd < 4)]
r["cheap"] = r.rv_fwd > r.iv
r["vratio"] = (r.rv_fwd ** 2) / (r.iv ** 2)
r["bucket"] = pd.cut(r["rank"], [-0.1, 10, 20, 30, 50, 70, 90, 100.1], labels=["0-10", "10-20", "20-30", "30-50", "50-70", "70-90", "90-100"])
g = r.groupby("bucket").agg(n=("iv", "size"), symbols=("sym", "nunique"), iv_med=("iv", lambda x: round(x.median() * 100, 1)),
                            rv_med=("rv_fwd", lambda x: round(x.median() * 100, 1)),
                            p_cheap=("cheap", lambda x: round(x.mean() * 100, 1)),
                            med_rv_over_iv=("rv_fwd", "size"))
g["med_rv_over_iv"] = r.groupby("bucket").apply(lambda x: round((x.rv_fwd / x.iv).median(), 3))
g["mean_var_ratio"] = r.groupby("bucket").apply(lambda x: round(x.vratio.clip(upper=25).mean(), 3))
print("observations", len(r), "symbols", r.sym.nunique(), "days", r.day.min(), "to", r.day.max())
print(g.to_string())
print("\noverall: P(rv_fwd > iv) %.1f%%, median rv/iv %.3f" % (r.cheap.mean() * 100, (r.rv_fwd / r.iv).median()))
# Same question for the IV-vs-HV reading: iv below trailing hv ("IV cheap vs realised").
r["iv_below_hv"] = r.iv < r.hv_now
print("\nwhen IV < trailing HV: n=%d, P(rv_fwd > iv)=%.1f%%; when IV >= HV: P=%.1f%%" % (
    r.iv_below_hv.sum(), r[r.iv_below_hv].cheap.mean() * 100, r[~r.iv_below_hv].cheap.mean() * 100))
# By month, to see whether one regime drives it.
r["month"] = r.day.str[:7]
print("\nP(cheap) by month, rank<=30 vs all:\n", r.groupby("month").apply(lambda x: pd.Series({
    "low_rank": round(x[x["rank"] <= 30].cheap.mean() * 100, 1), "all": round(x.cheap.mean() * 100, 1), "n": len(x)})).to_string())
g.to_csv(os.path.join(H, "ivrank_buckets.csv"))
