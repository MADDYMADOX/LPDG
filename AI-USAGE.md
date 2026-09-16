# AI usage

I used Claude (Claude Sonnet 5, in a pairing session) throughout this
project: exploring the data, designing and running the leak-free backtest,
scaffolding the pipeline code, generating the charts, and drafting this
documentation. Every module was reviewed and understood before being
accepted — not just accepted because it ran — since the live-session round
requires changing this code myself, live, in front of the people who wrote
the brief.

## What it was used for

- Reading `01-Challenge-Brief.pdf` / `02-Data-Dictionary.pdf` and cross-
  checking claims in them against the actual files (row counts, date
  ranges, encodings).
- Exploratory analysis: encoding checks, selection-bias analysis on
  `field_visits.csv`, quantifying the baseline's zero-variance blind spot,
  designing the leak-free backtest against `meter_read_success.csv`.
- Writing `src/io.py`, `src/scoring.py`, `src/predict.py`,
  `scripts/backtest.py`, `scripts/make_charts.py`, and the test suite.
- Drafting `DECISIONS.md`, `LIMITATIONS.md`, `REPORT.md`, and this file, from
  the numbers the backtest actually produced (not the other way around).

## One specific thing it got wrong

While diagnosing the `gateway_master.csv` mojibake (`Au�enmast` instead of
`Außenmast`), its first hypothesis was that the source file itself already
contained a corrupted/replacement character — i.e., that the bad byte was
baked into the file before we ever touched it. That was wrong: checking the
raw bytes showed a single valid Latin-1 byte (`0xDF`, the German sz) at that
position, not a Unicode replacement character. The real cause was that we
were about to *read* a Latin-1 file as UTF-8, not that the file was already
damaged. The distinction matters for the fix: "the file is corrupted" would
have sent us looking for a way to clean or discard bad rows, when the actual
fix is one line — decode with the correct encoding. I caught this by
checking `raw.decode("utf-8")` directly instead of trusting the first
explanation, which is why `src/io.py` now decodes `gateway_master.csv` with
`encoding="latin-1"` explicitly and documents why, rather than silently
coercing or dropping anything.

## A second thing it got wrong, caught on the last day

Preparing the walkthrough, I asked it to check the figures I was about to say
out loud. One of them — "53% of gateways have zero variance in `reboot_cnt`
over any 28-day window" — did not reproduce. 53.3% is real, but it is the
value at *one* window (28 days before 2025-12-01); the share is 44.6% early in
the history and **69.8% across the eight scored Mondays**, the window that
actually matters. The original number had been measured once and then written
up as though it were a constant, with "any 28-day window" doing the work.

That is the failure mode the brief calls claiming more than you measured, and
it would not have survived a reviewer recomputing it. The fix was to stop
quoting a single figure and commit the check instead:
`scripts/zero_variance_check.py` prints the share per metric per window, which
also surfaced something the single number had hidden — the blind spot is
specific to `reboot_cnt` (69.8%), while `offline_duration_sec` and
`disconnection_cnt` sit at 1.5%. That sharpens the point rather than weakening
it: the metric the given baseline leans on hardest is the one it is blindest
on.

## A smaller one, during development

 an early version of the
backtest script passed an already-timezone-aware `pandas.Timestamp` into
`pd.Timestamp(monday, tz="UTC")`, which raises (`Cannot pass a datetime or
Timestamp with tzinfo with the tz parameter`) — a real bug that surfaced
immediately on running it, not a subtle one, but worth naming since it's a
concrete instance of "ran it, it broke, fixed it" rather than everything
working on the first try.
