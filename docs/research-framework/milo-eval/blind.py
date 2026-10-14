"""Pair the two versions' answers per case, A/B at random, for a blinded review.

    python blind.py before after
Writes review/pairs.md (what the reviewer sees) and review/key.json (kept from it).
"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cases import CASES
a_label, b_label = sys.argv[1], sys.argv[2]
rng = random.Random(20261014)
os.makedirs(os.path.join(HERE, "review"), exist_ok=True)
key, parts = {}, ["# Blinded pairs\n"]
for c in CASES:
    x = open(os.path.join(HERE, "answers", a_label, c["id"] + ".md")).read().strip()
    y = open(os.path.join(HERE, "answers", b_label, c["id"] + ".md")).read().strip()
    flip = rng.random() < 0.5
    A, B = (y, x) if flip else (x, y)
    key[c["id"]] = {"A": b_label if flip else a_label, "B": a_label if flip else b_label}
    parts.append("## {} ({} on the {} page)\n\n**Question:** {}\n\n**A good answer must:** {}\n\n### Answer A\n\n{}\n\n### Answer B\n\n{}\n".format(
        c["id"], c["ticker"], c["view_label"], c["q"], "; ".join(c["must"]), A, B))
open(os.path.join(HERE, "review", "pairs.md"), "w").write("\n".join(parts))
json.dump(key, open(os.path.join(HERE, "review", "key.json"), "w"), indent=1)
print("wrote", len(key), "pairs")
