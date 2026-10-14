"""Build each case's Milo request with no model call, for before and after.

    python capture.py <worktree> <label>
"""
import asyncio, copy, json, os, sys
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))

BEFORE_KEYS = ["ticker", "quote", "verdict", "technicals", "gex", "greeks", "flow", "news",
               "entry_plan", "company", "naked_ideas", "strategy_ideas", "cases", "why", "whats_next",
               "pulse", "next_earnings_date", "sector_confirm", "earnings_momentum"]


def ctx_for(case, label):
    s = json.load(open(os.path.join(HERE, "swing-%s.json" % label)))
    ctx = {k: copy.deepcopy(s[k]) for k in BEFORE_KEYS if k in s}
    if label == "after":
        ctx["vol_surface"] = s.get("vol_surface"); ctx["iv_rank"] = s.get("iv_rank"); ctx["rate"] = s.get("rate")
        r = json.load(open(os.path.join(HERE, "research-after.json")))
        oc = {"source": "the contract table and position builder on the Options tab, from the delayed chain",
              "expiry": r["expiry"], "side": r["side"], "filters": r["filters"], "summary": r["summary"],
              "events": r["events"], "rate": r["rate"], "fetched_at": r.get("fetched_at"),
              "rows": [{k: row.get(k) for k in ("strike", "delta", "bid", "ask", "mid", "spread_pct", "iv_pct",
                        "breakeven_ask", "theta_per_contract", "vega_per_contract", "p_itm_model", "open_interest",
                        "volume")} | {"liquidity": row["liquidity"]["label"]} for row in r["table"]["rows"][:20]]}
        if case["position"]:
            a = json.load(open(os.path.join(HERE, "%s-after.json" % case["position"])))
            legs = [{k: l.get(k) for k in ("type", "side", "qty", "strike", "expiry")} for l in a["legs"]]
            oc["position"] = {"legs": legs, "analysis": {k: a.get(k) for k in (
                "entry", "max_profit", "max_profit_unbounded", "max_loss", "max_loss_unbounded",
                "breakevens_at_expiry", "greeks", "scenarios", "flags", "assumptions", "leg_liquidity")}}
        ctx["options_research"] = oc
    ctx["active_view"] = "swing"
    ctx["focus"] = {"scope": "auto", "view": "swing", "view_label": "Options", "ticker": "AAPL",
                    "captured_at": datetime.now(timezone.utc).isoformat()}
    ctx["data_as_of"] = s.get("generated_at")
    return ctx


def main(wt, label):
    sys.path.insert(0, wt); os.chdir(wt); sys.path.insert(0, HERE)
    from cases import CASES
    from app import ai
    out = os.path.join(HERE, "out", label); os.makedirs(out, exist_ok=True)
    for c in CASES:
        hist = [{"role": "user", "content": c["q"]}]
        kw, meta = ai.build_chat_request(hist, context=ctx_for(c, label), mode=c["mode"])
        sysblocks = [b["text"] for b in kw["system"]]
        json.dump({"id": c["id"], "system": sysblocks, "messages": kw["messages"]},
                  open(os.path.join(out, c["id"] + ".json"), "w"), default=str)
        print(c["id"], meta.get("level"), meta.get("horizon"), (meta.get("context") or {}).get("dropped"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
