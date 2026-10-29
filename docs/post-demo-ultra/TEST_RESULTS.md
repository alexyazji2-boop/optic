# Test results

Every entry gives the date and time (ET), the commit tested, the exact command or check script, and the
outcome as reported by the tool. Nothing here is summarised from memory. Working files (raw outputs, crawl
JSON, screenshots, scripts) are outside the public repository in
`~/Optic/work/post-demo-ultra-2026-10-29/`.

## Baseline (Phase 01), commit 9fa0f36 (origin/main, live)

### Tooling that exists in the repository

| Check the directive asks for | What the repository has | Result |
|---|---|---|
| Production build | None. No bundler or build step: `static/` is served as-is (CLAUDE.md). The deploy image is `Dockerfile` (python:3.12-slim); Docker is not installed on this machine, so the image was not built. | NOT TESTED (no build step; image build BLOCKED locally) |
| Type checker | None (no TypeScript, no mypy configuration). | not applicable |
| Linter | None configured (no ruff/flake8/eslint configuration). Ad-hoc substitute below. | ad-hoc only |
| Unit and integration tests | pytest suite in `tests/` (Python; client contracts read as text; some JS run under JavaScriptCore). | PASS, see below |
| Browser end-to-end tests | None in the repository. Earlier audits kept CDP check scripts outside it (`~/Optic/work/...`); this overhaul's copies are in `~/Optic/work/post-demo-ultra-2026-10-29/tools/`. | see crawl below |

### Commands and outcomes

| When (ET) | Command | Outcome |
|---|---|---|
| 2026-10-29 01:18:52 to 01:22:23 | `.venv/bin/python -m pytest -q -p no:cacheprovider` in `~/Optic/wt-ultra` | **7108 passed, 1 skipped, 6 warnings in 208.84 s**, exit 0. Warnings: urllib3 NotOpenSSLWarning (LibreSSL in the local Python 3.9), starlette per-request cookies deprecation (3, in tests/test_frontend_switch.py), pandas `'M'` FutureWarning (2, tests/test_valuation_inputs.py:212). The one skip is `tests/test_brokerage_exposure.py:586` ("reads EDGAR; set OPTIC_LIVE_EDGAR=1 to run"), a deliberate live-network test (confirmed with `pytest -rs tests/test_brokerage_exposure.py`). Raw: `baseline/pytest-baseline.txt`. |
| 2026-10-29 01:3x | `node --check` on every `.js` under `static/` (node v26.12.0) | **122 files, 0 failed** |
| 2026-10-29 01:3x | `.venv/bin/python -m compileall -q app tests` | ok |
| 2026-10-29 01:3x | `ruff 0.17.3 check --no-cache --select F --target-version py39 app` (pyflakes rules, run from a throwaway venv in the session scratchpad; not a repository tool) | **59 findings: 45 F401 unused import, 13 F841 unused local, 1 F811 redefinition; 0 undefined names.** Raw: `baseline/ruff-F-app.txt`. Logged as BUG-017, BUG-018. |
| 2026-10-29 01:2x | FastAPI route table read from `app.main.app.routes` | 241 routes, 231 under `/api`, 2 streaming (`/api/chat`, `/api/research`). Raw: `baseline/api-routes.json`, guards per handler in `baseline/route-guards.json`. |

### Environment differences worth knowing

- Local tests run on the shared venv's Python 3.9 (LibreSSL 2.8.3); production runs Python 3.12 in Docker. The
  suite cannot catch a 3.12-only failure.
- The local server (`optic-ultra`, :8250) uses a copy of the investor-audit data (`~/Optic/ultra-data`), the
  sandbox brokerage provider, background jobs off, and a stand-in for the Anthropic API on :8251. No real model
  key is used and nothing can be spent.

### Milo pipeline probe (stand-in model, so Optic's own pipeline only, never the real model's latency)

`tools/milo_probe.py`: signs in as the demo account, posts one question to `/api/chat`, times the SSE stream.

| Question, context | Headers (first byte) | First event | First text | Done | Events |
|---|---|---|---|---|---|
| "What happened to NVDA today?", NVDA (caches warm from the crawl) | 0.307 s | 0.322 s | 0.406 s | 0.794 s | assumed 1, status 1, retrieved 1, delta 10, done 1 |
| "What happened to KO today?", KO (cold) | 2.200 s | 2.213 s | 2.254 s | 2.626 s | same |
| "Explain this chart.", PEP (cold) | 1.466 s | 1.475 s | 1.535 s | 1.918 s | same |

Reading: the server streams real deltas, but nothing at all reaches the browser until the whole context is
built (`app/main.py` `/api/chat` gathers research, framework, chart levels and the linked portfolio before it
returns the `StreamingResponse`); cold, that is 1.5 to 2.2 s here before the model is even asked.

### Rendered crawl (Phase 01), 2026-10-29 01:22 to 01:47 ET, local server :8250 at 9fa0f36

Tool: `tools/crawl.py` (headless Chrome over CDP; kit from the 2026-10-27 audit plus a rendered-inventory probe),
`tools/classic_crawl.py`, `tools/summarize.py`. Raw: `crawl1/`.

| Pass | Loads | Script exceptions / console errors | Sideways overflow | Error states shown | Placeholder text | Notes |
|---|---|---|---|---|---|---|
| v2 guest, 56 routes x 1440/1280/768/390 | 224 | 0 (only the expected 404s on `#/ZZZZQ`) | 0 | 0 | 0 | `#/earnings?week=1` kept 7 skeletons past the 30 s cap on a cold server (BUG-016); `/api/dispersion`, `/api/implied-correlation`, `/api/stockmap` slow on first build |
| v2 signed in (demo account, owner on this server), same 56 x 4 | 224 | 0 | 0 | 1: `#/SPY/options` at 768, "The contracts did not load" after a Yahoo 503, a graceful state | 0 | `/api/brokerage/status` requested twice on every brokerage page |
| Classic guest, 26 views x 1440/390 | 52 | 0 | 0 | 0 | 0 | logos from unavatar.io blocked by ORB on `#/earnings` (BUG-028); `#/explore` empty at 1440 only (BUG-029) |
| Server log during all of the above | | 0 tracebacks, 0 HTTP 500 | | | | 6 Yahoo refusals (`401 Invalid Crumb`, `401 User is unable to access this feature`), all handled |

Density per route (guest, 1440): highest visible word counts Analysts 2,648, NVDA Financials 2,066, NVDA Investing 2,021
(268 controls), Insiders 1,620, Privacy 1,465, NVDA Overview 1,390 (177 controls), BRK-B 1,357, Retirement 1,322,
Home 1,135 (187 controls), NVDA Earnings 1,085, Read 1,033. Small touch targets flagged by the audit script at 390:
NVDA Investing 30, NVDA Overview 30, BRK-B 24, BTC 12. Contrast and unnamed-control counts were 0 on every load
(audit.js rules; Phase 10 re-measures with WCAG 2.2 tooling).
