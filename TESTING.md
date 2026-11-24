# Testing Optic

Two layers, one command each, both run by `.github/workflows/tests.yml` on every pull request and every push to
`main`. The count each run made is in the run's summary.

| Layer | Where | What it covers |
| --- | --- | --- |
| Python suite | `tests/*.py` | Routes through FastAPI's TestClient, the analytics, and the front end's modules run in JavaScriptCore or read as text (the project's pattern for client contracts, see CLAUDE.md) |
| Browser journeys | `tests/e2e/` | The real server in a subprocess and a real Chromium: Home and the stock page at each level, Show more, the level kept across reloads and devices, the Milo prompts and sign-in from them, Anthropic down, the first usage signal, the accessibility scan (WCAG 2.1 A and AA) and the keyboard |

## Running them from a fresh clone

Everything a run needs, and nowhere else:

- Python 3.12, and `python -m pip install -r requirements-dev.txt` (the app's own requirements plus the test tools)
- Chromium for Playwright: `python -m playwright install chromium`
- macOS for the full count: about a thousand tests run v2's modules in JavaScriptCore
  (`/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc`); without it they skip,
  which is why CI runs on a macOS runner
- `git` on the path (one test asks git what `.gitignore` covers)
- No network: pin outbound HTTP to a closed port so nothing can reach a real provider

```bash
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
python -m pytest -q                 # both layers
python -m pytest -q tests/e2e       # the browser journeys alone
```

The journeys start the app with `uvicorn` on a free local port and a fresh data directory. Anthropic is played by
`tests/support/anthropic_stub.py`, a recording stub on its own local port (`ANTHROPIC_BASE_URL`), which can answer,
time out or fail; every other provider host is refused at the closed port. The few symbol and quote answers the
stock page needs come from `tests/e2e/fixtures.py`, invented values labelled as such.

## Guarded surfaces added in this round, with the three legs

| Surface | No user | Wrong user | Wrong role |
| --- | --- | --- | --- |
| `GET /api/admin/usage-signals` (the owner's counts) | 401 | 403, a verified non-owner | 403, the owner's address unverified |
| `POST /api/usage` (the page's events) | allowed by design, counted by visitor id | the CSRF check when a session rides along | only the two page events; `milo_question` is the server's |

## Adding a test

A route: beside `tests/test_pass1_usage.py`, with the `accounts` fixture for a fresh database. A journey: in
`tests/e2e/`, opening its own browser context with `open_page` and its own account with `make_account`, so a rerun
never depends on what ran before.

## What no test drives

- Google, Apple and passkey sign-in: they need the providers' own pages and a real authenticator.
- Real market data: every feed is refused at the closed port, so panels that need one show their outage state.
- The live owner account on theopticterminal.com: the owner guard is tested with accounts the tests make.
