"""Build each case's Milo request with no model call, from one worktree.

    python capture.py <worktree> <label>

The browser side is the same for both versions (the tab's keys from the
snapshot); the server side is whatever that worktree adds (_augment_chat_context,
_with_research, and _with_framework where it exists).
"""
import asyncio, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TAB_KEYS = ["ticker", "quote", "verdict", "technicals", "gex", "greeks", "flow", "news", "entry_plan",
            "company", "cases", "why", "whats_next", "pulse", "next_earnings_date", "sector_confirm",
            "earnings_momentum", "vol_surface"]


def main(wt, label):
    sys.path.insert(0, wt); os.chdir(wt); sys.path.insert(0, HERE)
    from cases import CASES
    import app.main as m
    from app import ai
    if hasattr(m, "research_forecasts"):
        m.research_forecasts.DB_PATH = os.path.join(HERE, "out", label + "-forecasts.db")
    out = os.path.join(HERE, "out", label); os.makedirs(out, exist_ok=True)
    snaps = {}
    for c in CASES:
        t = c.get("ticker")
        ctx = {"active_view": c["view"],
               "focus": {"scope": "auto", "view": c["view"], "view_label": c["view_label"], "ticker": t,
                         "captured_at": datetime.now(timezone.utc).isoformat()}}
        if t not in snaps:
            snaps[t] = m._swing_snapshot(t, None, 2, True)
        ctx.update({k: snaps[t][k] for k in TAB_KEYS if k in snaps[t]})
        ctx["data_as_of"] = snaps[t].get("generated_at")
        hist = [{"role": "user", "content": c["q"]}]
        context = asyncio.run(m._augment_chat_context(hist, ctx))
        if hasattr(m, "_with_research"):
            context = asyncio.run(m._with_research(hist, context, None))
        if hasattr(m, "_with_framework"):
            m.FRAMEWORK_CHAT_SECONDS = 90.0     # the capture is not latency-bound
            context = asyncio.run(m._with_framework(hist, context, None))
        kw, meta = ai.build_chat_request(hist, context=context, mode=c["mode"])
        json.dump({"id": c["id"], "system": [b["text"] for b in kw["system"]], "messages": kw["messages"]},
                  open(os.path.join(out, c["id"] + ".json"), "w"), default=str)
        fw = (context or {}).get("framework") or {}
        print(c["id"], label, "mode", (fw.get("routing") or {}).get("mode"), "kept", (meta.get("context") or {}).get("kept"),
              "dropped", (meta.get("context") or {}).get("dropped"), "chars", (meta.get("context") or {}).get("chars"),
              "gaps", fw.get("gaps"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
