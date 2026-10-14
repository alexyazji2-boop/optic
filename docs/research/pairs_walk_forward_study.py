"""Walk-forward pairs test over classic pairs (cached daily bars)."""
import sys, os, json, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import pandas as pd
from app.analytics import pairs as pr
HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [("KO","PEP"),("XOM","CVX"),("V","MA"),("HD","LOW"),("GOOGL","GOOG"),("COHR","LITE"),("JPM","BAC"),("UPS","FDX"),
         ("MCD","YUM"),("WMT","TGT"),("MSFT","AAPL"),("GS","MS"),("LMT","NOC"),("CAT","DE"),("PG","CL"),("AMD","NVDA"),
         ("T","VZ"),("UNP","CSX"),("SPY","IVV"),("EWA","EWC")]
def load(s):
    p = os.path.join(HERE, "daily", s + ".csv")
    if not os.path.exists(p): return None
    df = pd.read_csv(p, index_col=0); df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York").tz_localize(None)
    return df
rows = []
for a, b in PAIRS:
    fa, fb = load(a), load(b)
    if fa is None or fb is None: print("missing", a, b); continue
    r = pr.run(a, b, fa, fb, json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
    wf = r["walk_forward"]; al, ct = wf["all"], wf["coint_only"]
    rows.append({"pair": a + "/" + b, "years": wf["years_traded"], "coint_share": wf["coint_share_pct"], "stayed": wf["stayed_coint_pct"],
                 "all": {k: al[k] for k in ("trades","total_return_pct","avg_trade_pct","win_rate_pct","cagr_pct","max_drawdown_pct","beats_random_pct")},
                 "coint": {k: ct[k] for k in ("trades","total_return_pct","avg_trade_pct","win_rate_pct","cagr_pct","beats_random_pct")},
                 "now": r["now"]})
    print("%-10s yrs %4.1f coint %5.1f%% held %5s | all n=%3d tot %+7.1f avg %+5.2f win %5s cagr %5s rnd %5s | coint n=%3d tot %+7.1f avg %5s | now z %5s lvl %s" % (
        a+"/"+b, wf["years_traded"], wf["coint_share_pct"], wf["stayed_coint_pct"], al["trades"], al["total_return_pct"], al["avg_trade_pct"] or 0, al["win_rate_pct"], al["cagr_pct"], al["beats_random_pct"],
        ct["trades"], ct["total_return_pct"], ct["avg_trade_pct"], r["now"]["z"], r["now"]["coint_level"]))
import numpy as np
allavg = [t for r in rows for t in [r["all"]["avg_trade_pct"]] if t is not None]
print("pairs with positive all-window total:", sum(1 for r in rows if r["all"]["total_return_pct"] > 0), "of", len(rows))
print("pairs with positive coint-only total:", sum(1 for r in rows if r["coint"]["trades"] and r["coint"]["total_return_pct"] > 0), "of", sum(1 for r in rows if r["coint"]["trades"]))
json.dump(rows, open(os.path.join(HERE, "study.json"), "w"), indent=1)
