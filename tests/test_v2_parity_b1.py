"""Classic parity, batch B1 (2026-10-21): the shell, quick fixes and the earnings-claim audit. The refresh loop's
rules and the report wording run in JavaScriptCore; the server's timing rule runs here. The interactions (the
week page, a section's last page, the bell and phone count, the More sheet, the sticky header, the in-place
price refresh) were driven in headless Chrome at 1440, 1024, 430, 390 and 360 (~/Optic/work/classic-parity/
b1_check.py, 78 checks, touch emulated). Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B1.
"""
import pandas as pd

from app.analytics import earnings as earn_mod
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"

FAKE = """
  let clock = 0, timers = [], hidden = false; const listeners = {};
  globalThis.setTimeout = (fn, ms) => { timers.push({ at: clock + ms, fn }); return timers.length; };
  globalThis.clearTimeout = (id) => { if (timers[id - 1]) timers[id - 1].fn = null; };
  globalThis.document = globalThis.document || {};
  Object.defineProperty(globalThis.document, 'hidden', { get: () => hidden, configurable: true });
  globalThis.document.addEventListener = (t, f) => { listeners[t] = f; }; globalThis.document.removeEventListener = (t) => { delete listeners[t]; };
  const advance = async (ms) => { const end = clock + ms; for (;;) { timers.sort((a, b) => a.at - b.at); const t = timers.find((x) => x.fn && x.at <= end); if (!t) break; clock = t.at; const fn = t.fn; t.fn = null; fn(); for (let i = 0; i < 6; i++) await Promise.resolve(); } clock = end; };
"""


def test_the_refresh_loop_never_overlaps_pauses_while_hidden_and_catches_up_once(tmp_path):
    got = _run(tmp_path, FAKE + """
      const P = await import('@POLL@');
      let runs = 0, applied = 0, slow = null;
      const p = P.poll(async (current) => { runs += 1; if (runs === 2) await new Promise((r) => { slow = r; }); if (current()) applied += 1; }, { every: 20000, closed: 300000, inSession: () => true });
      await advance(20000); const one = runs;
      await advance(20000); const two = runs;                       // the second run is still waiting
      await advance(40000); const stillTwo = runs;                  // never two at once
      slow(); for (let i = 0; i < 6; i++) await Promise.resolve();
      await advance(20000); const three = runs;
      hidden = true; await advance(60000); const hiddenRuns = runs;  // a hidden tab asks for nothing
      hidden = false; listeners.visibilitychange(); for (let i = 0; i < 6; i++) await Promise.resolve(); const back = runs;   // one catch-up on return
      p.stop(); await advance(100000); const stopped = runs;
      const q = P.poll(async () => {}, { every: 20000, closed: 300000, inSession: () => false });
      print(JSON.stringify({ one, two, stillTwo, three, hiddenRuns, back, stopped, applied,
        day: P.inTradingDay(new Date('2026-10-21T16:30:00Z')), night: P.inTradingDay(new Date('2026-10-21T04:47:00Z')), sat: P.inTradingDay(new Date('2026-10-24T16:30:00Z')) }));
      q.stop();
    """.replace("@POLL@", (JS / "core/poll.js").as_posix()))
    assert got["one"] == 1 and got["two"] == 2 and got["stillTwo"] == 2, "a slow refresh is never joined by another"
    assert got["three"] == 3
    assert got["hiddenRuns"] == 3, "a hidden tab runs nothing; the run that fell due is remembered"
    assert got["back"] == 4, "one catch-up on return"
    assert got["stopped"] == 4, "stopped means stopped"
    assert got["day"] is True and got["night"] is False and got["sat"] is False


def test_the_next_report_is_worded_from_what_is_known(tmp_path):
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "core/reports.js").as_posix()}');
      print(JSON.stringify({{
        flag: R.dateStatus({{ date: '2026-11-17', confirmed: true, confirmed_basis: 'yahoo_flag' }}),
        count: R.dateStatus({{ date: '2026-11-17', confirmed: true, confirmed_basis: 'date_count' }}),
        est: R.dateStatus({{ date: '2026-11-17', confirmed: false }}),
        habit: R.habitLine({{ usual_timing: {{ timing: 'after_close', count: 4 }} }}),
        short: R.habitLine({{ usual_timing: {{ timing: 'before_open', count: 2 }} }}),
        none: R.habitLine({{ timing: 'before_open' }}) }}));
    """)
    assert got == {"flag": "date confirmed by Yahoo Finance", "count": "date listed by Yahoo Finance", "est": "date not confirmed",
                   "habit": "Its last 4 reports came after the close.", "short": "", "none": ""}
    for page in ("pages/dossier.js", "pages/earnings.js"):
        src = (JS / page).read_text()
        assert "timing[nr.timing]" not in src, f"{page} states the coming report's session"


def test_the_server_never_times_a_report_that_has_not_happened():
    today = pd.Timestamp.today().normalize()
    day = lambda n: str((today + pd.Timedelta(days=n)).date())  # noqa: E731
    history = [{"date": day(27), "timing": "before_open", "eps_estimate": 2.47, "eps_reported": None}] + [
        {"date": day(-90 * k), "timing": "after_close", "eps_estimate": 1.0, "eps_reported": 1.1} for k in range(1, 5)]
    nr = earn_mod._next_report(history, {"dates": [day(27)], "confirmed": True, "confirmed_basis": "yahoo_flag"}, set())
    assert nr["date"] == day(27) and nr["timing"] is None, "Yahoo's time on an upcoming row is a placeholder (NVDA, AAPL 2026-10-21)"
    assert nr["usual_timing"] == {"timing": "after_close", "count": 4} and nr["confirmed_basis"] == "yahoo_flag"
    mixed = history[:2] + [{"date": day(-180), "timing": "before_open", "eps_reported": 1.0}] + history[3:]
    assert earn_mod._next_report(mixed, {"dates": [day(27)]}, set())["usual_timing"] is None, "an inconsistent habit is not a habit"
    yf = (V2.parent.parent / "app/providers/yf.py").read_text()
    assert '"confirmed": (not flag) if by_flag else len(dates) == 1,' in yf and 'get("isEarningsDateEstimate")' in yf


def test_the_shell_routes_and_names_from_b1():
    router = (JS / "core/router.js").read_text()
    assert "SLUG_VIEW.earnings = 'earningsweek';" in router and "'scenarios'" not in router
    assert "earningsweek: 'market'" in (JS / "nav.js").read_text()
    shell = (JS / "ui/shell.js").read_text()
    assert "const NAV_LAST = {};" in shell and "if (g && g.pages.some((p) => p.view === route.view)) NAV_LAST[g.id] = route.view;" in shell
    assert "row('#/signin', 'user', 'Sign in'" in shell and "store.user ? ''" in shell, "Sign in in More for a guest only"
    assert "t.setAttribute('aria-label', `Watchlist. ${words}`)" in shell, "the count's name starts with the visible word"
    assert "['ov:stages']" not in (JS / "core/milo-text.js").read_text() and "null]" not in (JS / "core/milo-text.js").read_text()
    assert '<a class="rail-row" href="#/research">Saved research</a>' in (JS / "app.js").read_text(), "B4d replaced the link to Classic"
    css = (V2 / "css/components.css").read_text()
    assert "html { scroll-padding-top: calc(var(--topbar-h, 72px) + var(--dstick-h, 0px) + var(--secidx-h, 0px) + 8px); }" in css   # B3 adds the section strip
    assert ".dstick { position: sticky; top: var(--topbar-h, 72px);" in css
