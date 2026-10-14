"""How often did the move to expiry exceed what the at-the-money straddle cost?

Weekly (each Monday, or the next session) from 2024-10 to 2026-09: on that
date, from DoltHub's option_chain, the first expiry 21 to 50 days out and the
strike nearest the close; straddle = call mid + put mid. Implied move =
straddle / spot. Realised = |close on (or just before) expiry / spot - 1|.
Output: per symbol, n, the share of times the realised move exceeded the
straddle, and the median of realised / implied.
"""
import json, os, sys, time, urllib.parse, urllib.request, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
API = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"
def q(sql):
    for attempt in range(3):
        try:
            req = urllib.request.Request(API + "?q=" + urllib.parse.quote(sql), headers={"User-Agent": "OpticTerminal research"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode())
            if d.get("query_execution_status") in ("Success", "RowLimit"):
                return d.get("rows") or []
        except Exception:
            pass
        time.sleep(5)
    return None
def fetch(syms, out_path):
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            r = json.loads(line); done.add((r["sym"], r["date"]))
    for sym in syms:
        px = yf.Ticker(sym).history(start="2024-09-01", auto_adjust=False)["Close"]
        px.index = px.index.tz_localize(None).normalize()
        mondays = pd.date_range("2024-10-07", "2026-08-31", freq="W-MON")
        for m in mondays:
            on = px.index[px.index >= m]
            if not len(on): continue
            d0 = on[0]; key = (sym, str(d0.date()))
            if key in done: continue
            spot = float(px.loc[d0])
            rows = q("SELECT expiration, strike, call_put, bid, ask FROM option_chain WHERE date = '%s' AND act_symbol = '%s' "
                     "AND expiration >= '%s' AND expiration <= '%s' AND strike >= %.2f AND strike <= %.2f" % (
                         d0.date(), sym, (d0 + pd.Timedelta(days=21)).date(), (d0 + pd.Timedelta(days=50)).date(), spot * 0.95, spot * 1.05))
            rec = {"sym": sym, "date": str(d0.date()), "spot": spot}
            if rows:
                df = pd.DataFrame(rows); df["strike"] = df.strike.astype(float)
                df["mid"] = (df.bid.astype(float) + df.ask.astype(float)) / 2
                exp = sorted(df.expiration.unique())[0]; e = df[df.expiration == exp]
                k = e.strike.iloc[(e.strike - spot).abs().argmin()]
                c = e[(e.strike == k) & (e.call_put == "Call")].mid; p = e[(e.strike == k) & (e.call_put == "Put")].mid
                if len(c) and len(p):
                    straddle = float(c.iloc[0] + p.iloc[0])
                    ex = pd.Timestamp(exp); after = px.index[px.index <= ex]
                    if ex <= px.index[-1] and len(after):
                        st = float(px.loc[after[-1]])
                        rec.update(expiry=exp, strike=float(k), straddle=straddle, implied=straddle / spot, realised=abs(st / spot - 1),
                                   days=int((ex - d0).days), strike_off=abs(k / spot - 1))
            with open(out_path, "a") as f: f.write(json.dumps(rec) + "\n")
        print("done", sym, flush=True)


def summarise(jsonl_path, out_path):
    """straddles.jsonl -> app/analytics/straddle_calibration.json.

    Samples a week apart on a ~25-day horizon overlap about four times, so the
    95% interval on the mean ratio uses a quarter of the count."""
    rows = [json.loads(l) for l in open(jsonl_path)]
    df = pd.DataFrame([r for r in rows if "implied" in r and r["implied"] > 0])
    df["ratio"] = df.realised / df.implied
    out = {}
    for sym, g in df.groupby("sym"):
        n = len(g)
        mean = float(g.ratio.mean())
        se = float(g.ratio.std(ddof=1)) / np.sqrt(max(1.0, n / 4.0))
        out[sym] = {"n": n, "from": g.date.min(), "to": g.date.max(), "mean_ratio": round(mean, 3),
                    "ci95": [round(mean - 1.96 * se, 3), round(mean + 1.96 * se, 3)],
                    "median_ratio": round(float(g.ratio.median()), 3),
                    "exceed_pct": round(float((g.realised > g.implied).mean() * 100), 1),
                    "implied_median_pct": round(float(g.implied.median() * 100), 2),
                    "days_median": int(g.days.median())}
    json.dump({"built": pd.Timestamp.now().strftime("%Y-%m-%d"),
               "source": "Derived from DoltHub post-no-preference/options option_chain, CC BY-SA 4.0",
               "source_url": "https://www.dolthub.com/repositories/post-no-preference/options",
               "method": ("Each Monday: the first expiry 21 to 50 days out, the strike nearest the close, the straddle's "
                          "mid as a share of the price, against the absolute move to that expiry's close. Mean ratio of "
                          "realised to implied with a 95% interval on a quarter of the samples (they overlap)."),
               "symbols": out}, open(out_path, "w"), indent=1)
    return out


if __name__ == "__main__":
    # python straddle_calibration.py fetch SPY,QQQ out.jsonl
    # python straddle_calibration.py summarise out.jsonl app/analytics/straddle_calibration.json
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2].split(","), sys.argv[3])
    else:
        summarise(sys.argv[2], sys.argv[3])
