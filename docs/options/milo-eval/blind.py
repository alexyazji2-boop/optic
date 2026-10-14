"""Build blinded A/B pairs of Milo answers for review.

    python3 blind.py            -> writes review/pairs.md and review/key.json

Each case shows the question, page, settings, the checks a good answer must
meet, and two answers labelled A and B in a random (seeded) order. key.json
maps each case's A/B back to before/after and is not given to the reviewer.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cases import CASES  # noqa: E402

LABELS = (os.environ.get("A_LABEL", "before"), os.environ.get("B_LABEL", "after"))
REVIEW = os.environ.get("REVIEW_DIR", "review")
rng = random.Random(20261012)
os.makedirs(os.path.join(HERE, REVIEW), exist_ok=True)
key, out = {}, ["# Blinded answer pairs\n"]
for c in CASES:
    ans = {}
    for lab in LABELS:
        p = os.path.join(HERE, "out", lab, "responses", c["id"] + ".md")
        ans[lab] = open(p).read().strip() if os.path.exists(p) else "(missing)"
    order = list(LABELS)
    rng.shuffle(order)
    key[c["id"]] = {"A": order[0], "B": order[1]}
    hist = "".join("\n> {}: {}".format(t["role"], t["content"].replace("\n", " ")[:300])
                   for t in c.get("history") or [])
    out.append("\n---\n\n## {id} ({persp})\n\nPage: {sym} {view}. Knowledge level setting: {mode}.{st}{hist}\n\n"
               "**Question:** {q}\n\n**A good answer:**\n{checks}\n\n### Answer A\n\n{a}\n\n### Answer B\n\n{b}\n".format(
                   id=c["id"], persp=c["persp"], sym=c.get("sym") or "AAPL", view=c.get("view", "options"), mode=c["mode"],
                   st=" Data captured {} minutes before the question.".format(c["stale_minutes"]) if c.get("stale_minutes") else "",
                   hist=("\n\nEarlier turns:" + hist) if hist else "", q=c["q"],
                   checks="\n".join("- " + x for x in c["checks"]), a=ans[order[0]], b=ans[order[1]]))
open(os.path.join(HERE, REVIEW, "pairs.md"), "w").write("".join(out))
json.dump(key, open(os.path.join(HERE, REVIEW, "key.json"), "w"), indent=1)
print("pairs:", len(CASES))
