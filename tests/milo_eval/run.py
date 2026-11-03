"""Run Milo's evaluation suite on fixtures and write the report (post-demo Phase 08, 2026-10-29; ported by hand from
the milo-upgrade branch's tests/milo_eval/run.py at 55721f6).

    .venv/bin/python -m tests.milo_eval.run [--out DIR] [--only ID-PREFIX]

Writes DIR/results.json (every check of every case) and DIR/REPORT.md (the metrics directive 08 section 10 asks to
track). Nothing here calls a model or the network: the answer-level checks are listed as not executed, with the
reason. `tests/milo_eval/run_model.py` runs the same cases against a model when one can be called.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("WATCH_AUTO", "false")

from tests.milo_eval import harness, checks          # noqa: E402
from tests.milo_eval.cases import (CASES, CATEGORIES, SUITES, BENCH_VERSION, FAMILY_DIMENSION, DIMENSIONS,  # noqa: E402
                                   ANSWER_DIMENSION)

# Anthropic's list price for the chat model (app/ai.py PULSE_MODEL, claude-sonnet-5-5), per million tokens, as the
# 2026-10-16 live trial recorded it (docs/milo/reasoning-eval/LIVE-MODEL-TRIAL.md: $2 in, $10 out); a cache read at
# $0.10, as Anthropic's pricing page read on 2026-10-30 gives it and app/ai_store.py prices it (BUG-176; $0.20 before
# Phase 11, BUG-180). No tokenizer is reachable here, so characters are turned into tokens by a rule of thumb.
PRICE_IN, PRICE_OUT, PRICE_CACHED = 2.0, 10.0, 0.1
CHARS_PER_TOKEN = 3.6
FAMILIES = ("tool_selection", "factual_support", "calculation", "freshness", "authorization", "injection",
            "citation_plumbing", "policy", "level", "budget")


def estimate_cost(got):
    """Input split into the cached prefix (the base prompt) and the rest, plus an assumed 600-token answer per round
    and one tool round on average. An estimate, labelled as one in the report."""
    system = (got.get("kwargs") or {}).get("system") or []
    cached = len(system[0]["text"]) if system and isinstance(system[0], dict) else 0
    rest = got["input_chars"] - cached
    rounds = 2
    tin = rest / CHARS_PER_TOKEN * rounds
    tcache = cached / CHARS_PER_TOKEN * rounds
    tout = 600 * rounds
    return (tin * PRICE_IN + tcache * PRICE_CACHED + tout * PRICE_OUT) / 1e6, int(tin + tcache), tout


def run(only=None):
    results = []
    for case in CASES:
        if only and not case["id"].startswith(only):
            continue
        row = {"id": case["id"], "category": case["category"], "question": case["question"], "checks": [], "error": None,
               "answer_checks": case["answer_checks"], "unacceptable": case["unacceptable"],
               # the directive's case fields (Phase 12): what the case expects and what it scores
               "suite": case["suite"], "risk": case["risk"], "difficulty": case["difficulty"], "behavior": case["behavior"],
               "refs": case["refs"], "scoring": case["scoring"], "authorized_tools": case["authorized_tools"],
               "level": case.get("mode"), "user": case.get("user"), "turns": len(case.get("history") or []) + 1}
        try:
            got = harness.assemble(case)
            row["checks"] += checks.check_assembly(case, got)
            row["assembly_seconds"] = got["seconds"]
            cost, tin, tout = estimate_cost(got)
            row.update(est_cost=cost, est_input_tokens=tin, est_output_tokens=tout, input_chars=got["input_chars"],
                       tools_offered=got["tools"], context_keys=sorted((got["context"] or {}).keys()),
                       policy_kinds=(got["meta"] or {}).get("policy_kinds") or [])
            for call in case["tool_calls"]:
                res = harness.run_tool(case, call["name"], call["args"])
                row["checks"] += checks.check_tool(case, call, res)
                row.setdefault("tool_seconds", []).append(round(res["seconds"], 4))
        except Exception as exc:                                      # a crash is a failed case, never a skipped one
            row["error"] = "{}: {}".format(type(exc).__name__, exc)
        results.append(row)
    return results


# A failed check that would be a critical defect in an answer (directive 14 Part 7.2): another reader's data, a forged
# or injected value treated as Optic's, a secret, or a wrong figure handed to the model as verified
CRITICAL_FAMILIES = ("authorization", "injection", "calculation")


def summarise(results):
    fam = defaultdict(lambda: [0, 0])
    cat = defaultdict(lambda: [0, 0])
    failures = []
    for r in results:
        ok_case = r["error"] is None and all(c[2] for c in r["checks"])
        cat[r["category"]][0] += ok_case
        cat[r["category"]][1] += 1
        for f, name, passed, detail in r["checks"]:
            fam[f][0] += passed
            fam[f][1] += 1
            if not passed:
                failures.append((r["id"], f, name, detail))
        if r["error"]:
            failures.append((r["id"], "error", "case crashed", r["error"]))
    return fam, cat, failures


def by_suite(results):
    out = defaultdict(lambda: [0, 0])
    for r in results:
        out[r["suite"]][0] += r["error"] is None and all(c[2] for c in r["checks"])
        out[r["suite"]][1] += 1
    return out


def dimensions(fam):
    """The directive's eight scores, 0 to 100, from the request-level families that feed each. A dimension that only
    an answer can show has no request-level checks and is reported as not executed, never as a score."""
    dims = {d: [0, 0] for d in DIMENSIONS}
    for f, (p, n) in fam.items():
        d = FAMILY_DIMENSION.get(f)
        if d:
            dims[d][0] += p
            dims[d][1] += n
    return dims


def report(results, out: Path, started: float):
    fam, cat, failures = summarise(results)
    lat = [r["assembly_seconds"] for r in results if r.get("assembly_seconds") is not None]
    tool_lat = [s for r in results for s in r.get("tool_seconds", [])]
    costs = [r["est_cost"] for r in results if r.get("est_cost") is not None]
    toks = [r["est_input_tokens"] for r in results if r.get("est_input_tokens")]
    chars = [r["input_chars"] for r in results if r.get("input_chars")]
    lines = ["# Milo evaluation suite: report", "",
             "Run {} on fixtures (`tests/milo_eval`), {} cases, {:.0f} s. No model was called.".format(
                 time.strftime("%Y-%m-%d %H:%M"), len(results), time.time() - started), "",
             "## Automated checks (executed)", "", "| Family | Passed | Checks |", "|---|---|---|"]
    for f in FAMILIES:
        p, n = fam.get(f, [0, 0])
        lines.append("| {} | {} | {} |".format(f, p, n))
    lines += ["", "## Scores by the directive's dimensions (request level, 0 to 100)", "",
              "Each dimension is the share of request-level checks that feed it which passed. Answer relevance and context",
              "correctness beyond what the request carries need an answer, so they are not scored here.", "",
              "| Dimension | Score | Checks |", "|---|---|---|"]
    for d, (p, n) in dimensions(fam).items():
        lines.append("| {} | {} | {} |".format(d, "{:.1f}".format(100.0 * p / n) if n else "not executed (needs a model)", n))
    crit = [f for f in failures if f[1] in CRITICAL_FAMILIES or f[1] == "error"]
    lines += ["", "## Critical failures (reported apart, never averaged in)", ""]
    lines += ["* {} [{}] {}: {}".format(*f) for f in crit] or ["None."]
    lines += ["", "## The directive's suites (Part 4.3)", "", "| Suite | Cases passing every check | Cases | Minimum |", "|---|---|---|---|"]
    bs = by_suite(results)
    for k, (name, mn) in SUITES.items():
        p, n = bs.get(k, [0, 0])
        lines.append("| {} | {} | {} | {} |".format(name, p, n, mn))
    lines += ["", "| Category | Cases passing every check | Cases |", "|---|---|---|"]
    for c in CATEGORIES:
        p, n = cat.get(c, [0, 0])
        lines.append("| {} ({}) | {} | {} |".format(CATEGORIES[c], c, p, n))
    lines += ["", "## Latency (measured, fixtures, no network, no model)", "",
              "* Request assembly through `/api/chat`: median {:.3f} s, p95 {:.3f} s, max {:.3f} s ({} cases).".format(
                  statistics.median(lat), sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], max(lat), len(lat)) if lat else "* none",
              "* Tool calls through the toolbox: median {:.4f} s, max {:.3f} s ({} calls).".format(
                  statistics.median(tool_lat), max(tool_lat), len(tool_lat)) if tool_lat else "* none",
              "", "## Request size and estimated cost per answer (sizes measured, tokens and cost estimated)", "",
              "* Characters sent per request (system prompt, CONTEXT, tools): median {:,}, max {:,}.".format(
                  int(statistics.median(chars)), max(chars)) if chars else "",
              "* Estimated input per answer {:,} tokens median (two model rounds, base prompt cached), output 1,200 tokens assumed.".format(
                  int(statistics.median(toks))) if toks else "",
              "* Estimated cost per answer: median ${:.4f}, max ${:.4f}, at $2 / $10 per million tokens in / out and cached input at $0.10.".format(
                  statistics.median(costs), max(costs)) if costs else "",
              "", "## Answer-level checks (not executed)", "",
              "{} answer checks are defined across the cases (`answer_checks.py`), with {} outcomes named unacceptable. None ran: no "
              "model can be called on this machine (BLOCKERS BL-01), so there are no answers to check. Correctness of "
              "answers, unsupported claims in answers, advice in answers and answer quality are therefore NOT TESTED; the "
              "request-level checks above are what was measured.".format(
                  sum(len(r["answer_checks"]) for r in results), sum(len(r["unacceptable"]) for r in results)),
              "", "## Failures", ""]
    lines += ["* {} [{}] {}: {}".format(*f) for f in failures] or ["None."]
    out.mkdir(parents=True, exist_ok=True)
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    return failures


def archive_dir(root: Path) -> Path:
    """docs/ai/eval-results/<benchmark version>/<UTC time>-<commit>: one folder per run, never overwritten, so a later
    run is compared with the earlier ones rather than replacing them (directive 14 Part 4.7)."""
    import subprocess
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return root / "docs" / "ai" / "eval-results" / BENCH_VERSION / "{}-{}{}".format(stamp, sha or "nogit", "-dirty" if dirty else "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.environ.get("MILO_EVAL_OUT", "milo-eval-out"))
    ap.add_argument("--only")
    ap.add_argument("--archive", action="store_true", help="also keep this run under docs/ai/eval-results/")
    a = ap.parse_args(argv)
    t0 = time.time()
    res = run(a.only)
    failures = report(res, Path(a.out), t0)
    if a.archive:
        dest = archive_dir(Path(__file__).resolve().parents[2])
        report(res, dest, t0)
        print("archived to", dest)
    print((Path(a.out) / "REPORT.md").read_text())
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
