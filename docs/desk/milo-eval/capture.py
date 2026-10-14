"""Build each case's Milo request, with no model call, from one worktree.

    python capture.py <worktree> <label>

The browser's side of the context is built the same way for both versions:
the snapshot the reader's open tab would hold (the same keys the tab sends),
the focus line and the view. The server's side is whatever that worktree's own
code adds: `_augment_chat_context`, and `_with_research` where it exists. So the
difference between before and after is the retrieval and the instructions,
not the data the browser had.
"""
import asyncio, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TAB_KEYS = ["ticker", "quote", "verdict", "technicals", "gex", "greeks", "flow", "news", "entry_plan",
            "company", "cases", "why", "whats_next", "pulse", "next_earnings_date", "sector_confirm",
            "earnings_momentum"]


def main(wt, label):
    sys.path.insert(0, wt); os.chdir(wt); sys.path.insert(0, HERE)
    from cases import CASES
    import app.main as m
    from app import ai
    out = os.path.join(HERE, "out", label); os.makedirs(out, exist_ok=True)
    snaps = {}
    for c in CASES:
        t = c.get("ticker")
        ctx = {"active_view": c["view"],
               "focus": {"scope": "auto", "view": c["view"], "view_label": c["view_label"], "ticker": t,
                         "captured_at": datetime.now(timezone.utc).isoformat()}}
        if t:
            if t not in snaps:
                snaps[t] = m._swing_snapshot(t, None, 2, True)
            ctx.update({k: snaps[t][k] for k in TAB_KEYS if k in snaps[t]})
            ctx["data_as_of"] = snaps[t].get("generated_at")
        if c.get("desk"):
            # What the Read page holds. Before, there is no edition: the reader
            # has the old desk note in front of them. After, the edition and
            # the section asked about.
            if label.startswith("after"):
                served = m.desk_edition_mod.served(datetime.now(timezone.utc), m.session_mod)
                ed = served.get("edition") or {}
                ctx["desk_edition"] = {"key": ed.get("key"), "date": ed.get("date"), "slot": ed.get("slot"),
                                       "headline": ed.get("headline"), "summary": (ed.get("summary") or {}).get("text"),
                                       "is_today": served.get("is_today"), "voice": ed.get("voice"),
                                       "sections": [s.get("id") for s in ed.get("sections") or []]}
                ctx["desk_section"] = {"key": ed.get("key"), "section": c["desk"]}
            else:
                desk = m._morning_desk(None)
                ctx["morning_desk"] = {k: desk.get(k) for k in ("date", "lead", "scenarios", "note", "overall",
                                                                  "calendar", "limits")}
        hist = [{"role": "user", "content": c["q"]}]
        context = asyncio.run(m._augment_chat_context(hist, ctx))
        if hasattr(m, "_with_research"):
            context = asyncio.run(m._with_research(hist, context, c.get("horizon")))
        kw, meta = ai.build_chat_request(hist, context=context, mode=c["mode"], horizon=c.get("horizon"))
        json.dump({"id": c["id"], "system": [b["text"] for b in kw["system"]], "messages": kw["messages"]},
                  open(os.path.join(out, c["id"] + ".json"), "w"), default=str)
        research = (context or {}).get("research") or {}
        json.dump(research, open(os.path.join(out, c["id"] + ".research.json"), "w"), default=str, indent=1)
        print(c["id"], label, "intent", research.get("intent"), "items", len(research.get("items") or []),
              "dropped", (meta.get("context") or {}).get("dropped"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
