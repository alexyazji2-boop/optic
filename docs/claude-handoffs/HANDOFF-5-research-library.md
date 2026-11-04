# Handoff 5: the Saved Research Library

Branch `handoff-5-research-library`, cut from `main` at c623c264 on 2026-11-04. It does not depend on Handoffs 1 to 4
and can be reviewed and merged on its own. Not deployed.

## What was missing

The authenticated audit of 2026-11-03 (defect 6) found that research had no home. A comparison, a Milo conversation or a
research sheet could not be kept and returned to as one thing. What the code had, verified:

| What existed | Where | What it lacked |
|---|---|---|
| A `saved_research` table, account-private, with a plan limit (40 free) | `app/db.py`, `app/account.py` `/api/saved-research` | It kept questions to ask again (`content` text, one `symbol`), nothing else. Classic reads it as exactly that. |
| A "Saved research" page | `#/research`, `pages/saved.js` | Questions only; in no navigation group, reached from the account menu and the palette. |
| Milo's conversations | this browser's `optic.pulse.history.v1`, 30 kept | Never on the account, and without the sources behind each answer: those were kept in memory for the session only. |
| Watchlists, theses, valuations | tables of their own | Not research items. |

## What was built

**One record per saved item, in the existing table.** Migration 20 adds `tickers`, `ref`, `summary`, `payload` and
`item_key` to `saved_research`. The plan's limit, cascade deletion with the account and the volume backups therefore
cover it already. A row saved before has `item_key` NULL and stays a question. The handoff's fields:

| Handoff field | Column |
|---|---|
| id | `id` |
| owner | `user_id` |
| type | `research_type` |
| tickers | `tickers` |
| payload reference | `ref` and `summary` |
| name | `title` |
| created and updated | `created_at`, `updated_at` |

**Kept by reference where the thing still exists, by copy where it must not change:**

| Kind | Saved from | Kept | Reopens |
|---|---|---|---|
| Company | Dossier header, beside Watch (every tab) | the ticker and tab; its name and the price when saved | its Dossier tab, on today's figures |
| Comparison | Compare, beside the controls and beside "Optic's take" | the tickers and their names | Compare with those tickers |
| Research sheet | the sheet's actions (not printed) | the ticker; its name and price when saved | the sheet, on today's figures |
| Milo conversation | Milo's header, as an icon | every message, and each answer's sources (cited, read, retrieved, loaded) with the times they were read and the page it was asked from | Milo's panel, about the same ticker |
| Question | Milo's Save under a question (as before) | the question | Milo's box, unsent |

**The API** (`app/library.py`, all signed in, writes behind the CSRF pair):

- `GET /api/library`: newest first, 30 a page with a cursor.
  - Filters: by kind; by `q`, which searches names, tickers and the text; by `key`, which is how a Save button asks whether its thing is saved.
  - Counts by kind, and the plan's limit.
  - Each item says which of its tickers are no longer available.
  - A conversation's copy is not in the list.
- `GET /api/library/{id}`: one item in full, including a conversation's copy.
- `POST /api/library`: saves one item.
  - A second save of the same thing (same company or sheet, the same set of tickers in any order, the same conversation) answers 409 with the saved one.
  - `on_duplicate: "update"` gives the saved item this save's contents and today's date, keeping its name.
  - `on_duplicate: "copy"` keeps another item under the name given.
- `PATCH /api/library/{id}` renames, without changing the saved date.
- `DELETE /api/library/{id}` deletes.
- Another account's item is 404, never 403.

**Size limits:** names 120 characters; summaries 6,000; a conversation 200,000 with 60 messages. A conversation keeps
only the fields listed, each cut to a length, so a save cannot carry anything else.

**Whether a ticker is still there** (`library.listed`):
- the exchange directory first;
- for a symbol it does not list, the quote source: a trade in the last ten days counts, so an over-the-counter listing such as TCEHY stays;
- no price at all, from both, is "no longer available";
- a source that fails is "cannot tell", never "gone".

An answer is kept an hour.

**The Save control** (`ui/library.js`, with the API in `core/library.js`):
- **Saving.** One press saves under the ticker(s) and the date in the reader's timezone ("AAPL, Nov 4, 2026"), and the toast offers Rename.
- **Saved state.** It is a toggle like Watch: "Saved" in the active fill, never gold. Pressing it shows the saved item, with Rename, Update with what is on screen, Open Saved research and Delete. Delete asks twice.
- **Duplicates.** A duplicate opens "Already saved": update the saved one, or save a copy under a name.
- **Failures.** A failed save says so beside the button ("Not saved: … Retry"), and the button stays "Save".
- **Everywhere at once.** Every Save button for one thing follows a save, rename or delete made anywhere on the page.

**The library** (Saved research, `#/research`):
- **Filters.** A filter by kind with counts, and a search that keeps its focus while the list updates.
- **Each item.** Its kind, name, what it is about, its tickers and the date saved (and updated). It has Open, Rename and Delete, each 44 px on a phone, in one column.
- **Pages.** "Show more" loads the next page.
- **Empty state.** It explains what can be saved and links to a Dossier.
- **Loading.** It ends like Home's panels (Handoff 4): after 10 seconds, "Couldn't load your saved research." with Retry, then automatic retries 5, 15 and 45 seconds apart, then only on Retry.
- **Guests.** A guest keeps this browser's questions, as before, and is told the library is kept with an account.

**Reopening a Milo conversation:**
- It loads the saved copy then, not with the list.
- It opens Milo's panel about the saved ticker, with the note "Saved on Nov 4, 2026 at 3:20 pm EST; figures as of then. Each answer keeps the sources it had and when they were read."
- Every source time not from today says its day ("observed Oct 28, 3:41 pm"). This now holds in Milo generally, not only for saved answers.
- Nothing is sent: a follow-up is a new question, about the same ticker. Saving it again offers to update the saved one.

**A ticker that goes:**
- *A company or a sheet:* its row says "AAPL is no longer available", with the name and price when saved. Its Open is disabled.
- *A comparison:* it opens with the tickers that remain, and Compare says the missing ticker "was in this saved comparison and is no longer available, so it was left out".

## Acceptance tests (Handoff 5)

`tests/test_research_library.py`:

- **Save from Dossier, Compare and Milo; all three appear in the library and reopen with correct ticker context.**
  `test_acceptance_1_*` builds each save from the page's own code: the Dossier header's provider, the Compare page
  after a comparison, and Milo's `conversationSpec`. It saves all three, lists them, and reopens each: `#/AAPL/chart`,
  `#/compare?t=AAPL,MSFT`, and Milo about AAPL with the conversation's own id. The research sheet is tested too.
- **Delete removes the item everywhere; a duplicate save does not duplicate.** `test_acceptance_2_*`:
  - Delete: the item is gone from the list, from a key lookup and from the counts, and every Save button for it turns back to "Save".
  - Duplicates: the same comparison in another order answers 409; "update" keeps one item and its name; "copy" makes a second only when asked.
  - The control: a failed save shows "Not saved: … Retry" and is never shown as saved.
- **A saved Milo conversation keeps its original sources and as-of dates on reopen.** `test_acceptance_3_*` saves a
  conversation with cited, retrieved and loaded sources, and reads it back unchanged. Reopened, it says when it was
  saved, each source keeps its day ("observed Oct 28, 2:46 pm"), and saving it again carries the same sources.
- **The library is private per account.** `test_acceptance_4_*`:
  - Another account gets 404 on read, rename and delete, its key lookups find nothing, and its "update" never reaches the first account's item.
  - A user id in the body is ignored; a guest gets 401 everywhere; a write without the CSRF pair gets 403.
  - A check that every SQL statement in `app/library.py` is bound to the owner and none is built from input.
- **Edge cases:** a ticker that goes (company, comparison, over the counter, a failing source), pages and search
  (with a literal `%`), what a save may carry (sizes, kinds, roles, extra fields), the plan's limit, the questions saved
  before (in the library, and Classic's list unchanged), the migration on a database with questions in it, no saving
  without a press, the library's own loading, and the phone layout.

## Live check, 2026-11-04 (local server on this branch, a fresh local test account, real market data)

- **Dossier:** at a narrow width, Save sits in the header's one row beside Watch, above the fold. Pressed, it said "Saved to Saved research as “AAPL, Nov 4, 2026”." and turned to "Saved".
- **Compare:** after AAPL and MSFT ran, the page scrolled to its take, where "Save comparison" sits beside "Ask Milo about this comparison". Pressed, both Save buttons turned to "Saved", and the item was named "AAPL vs MSFT, Nov 4, 2026".
- **Milo:** Milo is switched off on the local server (no model key), so a conversation with sources was saved through the API and reopened from the library.
  - The panel said "Saved on Nov 4, 2026 at 3:20 pm EST; figures as of then."
  - The answer's line said "asked from NVDA Dossier, Overview, Oct 28, 3:41 pm", and its sources "observed Oct 28, 3:41 pm" and "observed Oct 27, 4 pm".
  - Milo's context was NVDA.
  - A conversation from Milo's history was then saved from Milo's own header button ("SPY, Nov 4, 2026"). Pressing it again showed the saved item, and Update kept it one item.
- **Research sheet:** "Save sheet" saved NVDA's sheet; `#/research?kind=sheet` listed it, and Open went to `#/NVDA/sheet`.
- **Library page:**
  - The kind filter and search worked, and the search box kept its focus.
  - Rename worked.
  - Delete took two presses, after which AAPL's Dossier showed "Save" again.
  - Open went to `#/compare?t=AAPL,MSFT`.
- **A ticker that went:** a comparison of NVDA and a symbol with no listing and no price said "… is no longer available. It opens with NVDA alone". It opened Compare with NVDA and the note.
- **Library loading:** with the library's requests made to hang, it said "Couldn't load your saved research. It has not answered in 10 seconds." at 10 s, and Retry brought the list back.
- **Phone width:** no sideways scroll. The pane was hidden for part of the check, so those results were read from the page rather than screenshots.

## Decisions for review

1. **No navigation entry.** The library is Saved research at `#/research`, as before, reached from the account menu,
   the palette (now also found by "library", "comparisons", "conversations" and "sheets") and the Save sheet's "Open
   Saved research". Adding it to the sidebar is a navigation change, which needs your yes. If you want one, a "Saved
   research" tab under Watchlist (beside Watchlist and Alerts) would fit.
2. **One table, not a new one.** Library items are `saved_research` rows, so the plan's limit counts them with saved
   questions: 40 on the free plan, 1,000 and 10,000 on the paid ones.
3. **A conversation is a copy; everything else is a reference.** A company, a comparison or a sheet reopens on today's
   figures, with its name and price when saved shown if its ticker goes. A conversation keeps its words and sources as
   they were. This follows the handoff, and Classic's rule that a stored answer is never shown as current.
4. **Only a conversation opened in this session has its sources.** Milo's browser history never kept them, so a
   conversation reopened from that history and then saved has its words but no sources.
5. **Updating a duplicate keeps its name** and gives it today's date and contents; a copy needs its own name.
6. **Deleting asks twice and cannot be undone.** There is one copy, the account's; it goes from every device.

## Found and not fixed here

1. **Classic** lists questions only. Library items do not appear there, by design, so it is unchanged.
2. **Sharing** is deferred by the handoff.
3. **Milo's own history** stays in this browser. Persisting each answer's sources there would let any reopened
   conversation be saved with them; it is a change to Milo's storage, not the library.
4. **Search** reads the first 2,000 characters of a conversation's text; a full-text index would read all of it.
