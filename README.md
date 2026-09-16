# LPDG Innovation Hub 2026 — Selection Challenge

Which 15 gateways to visit each week, and why.
**Part 2 track: Data science.**

## Walkthrough recording

<!-- REPLACE THE LINE BELOW WITH YOUR UNLISTED YOUTUBE / VIMEO / DRIVE LINK.
     Test it in a private browser window first: a link that needs an access
     request counts as no recording. -->

**▶ 6–8 minute walkthrough: _link to be added_**

What is in it: the ranking method and why it is not a trained model, the
leak-free backtest behind `REPORT.md`, the two real bugs in this data, and a
live run from `data/` to a validated `predictions.csv`.

## Run it

You need Python 3.11+ and the provided data. Put the `data` folder exactly as
provided at the repository root first — it is git-ignored and not shipped here,
because the dataset is not ours to publish.

```
python run.py
```

That is the whole thing. It builds `predictions.csv` at the repository root and
then runs the official `validate_submission.py` over it; a non-zero exit code
means the file would not be accepted, and it has already printed why. If the
dependencies are not installed, `run.py` creates a local `.venv`, installs the
pinned versions from `requirements.txt` into it, and re-runs itself there — so a
clean clone needs nothing but an interpreter. Nothing on the path from `data/`
to `predictions.csv` touches the network.

Expected output:

```
wrote predictions.csv -- 120 rows over 8 weeks
predictions.csv: OK
  15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
```

<details>
<summary>Other ways to run it</summary>

Already have the dependencies, or prefer your own environment:

```
pip install -r requirements.txt
python run.py --no-venv
```

Or call the two steps directly:

```
python -m src.predict --data data --out predictions.csv
python validate_submission.py predictions.csv
```

In Docker:

```
docker compose up --build
```

Honest note: the Docker path is written and reviewed but **not verified on the
development machine**, which has no WSL backend and so cannot start Docker's
Linux engine. `python run.py` is the path that has actually been run end to end,
and it is the one to use. Both go through the same entry point.

</details>

## A new month of data

The submission window is fixed — `validate_submission.py` hard-codes the eight
Mondays from 2026-02-02 to 2026-03-23 — so `python run.py` always scores exactly
those weeks, however much data is present.

Nothing else in the pipeline is pinned to those dates. Drop a new
`data/telemetry/month=YYYY-MM/` partition in and:

- the default run says so on stderr rather than ignoring it silently:
  `note: telemetry runs to 2026-03-31, past the end of the scored window ...`
- `python run.py --auto-window` scores the most recent 8 Mondays the data
  supports instead. (The official validator is skipped there, since it only
  knows about the submission window.)

`python -m src.predict --start 2026-03-02 --weeks 4` picks any window explicitly.

## Reproducing the analysis

```
python scripts/backtest.py      # writes scripts/backtest_results.csv
python scripts/make_charts.py   # writes report/figures/*.png
python -m pytest tests/ -q
```

The scoring tests build their own small synthetic fixtures and run anywhere.
The loader and end-to-end tests need the real dataset and **skip cleanly** when
`data/` is absent, rather than erroring — so `pytest` is safe to run on a fresh
clone. With the data present, all 12 pass.

## What this is

- `run.py` — the one command: check inputs, rank, validate.
- `src/io.py` — loaders, each one validating its own assumptions about the file
  it reads instead of trusting it blindly (see the encoding bug below).
- `src/scoring.py` — the ranking method: a leak-free blend of a 3-sigma
  telemetry-anomaly signal and a lagged meter-read-success trend.
- `src/predict.py` — builds `predictions.csv` for the 8 scored weeks.
- `scripts/backtest.py` — the honest, leak-free historical backtest this method
  is justified by (21 weeks, 4 different definitions of "needs a visit,"
  bootstrapped confidence intervals).
- `tests/` — including regression tests for two real bugs found in this data.

## Read these

| File | What is in it |
| --- | --- |
| `REPORT.md` | The findings, with charts, aimed at the operations manager. |
| `DECISIONS.md` | Five choices, the alternative rejected for each, and why. |
| `LIMITATIONS.md` | What this cannot do, and what two more weeks would buy. |
| `AI-USAGE.md` | What AI was used for, and one thing it got wrong that I caught. |

## Two things this data will do to you

1. `gateway_master.csv` is Latin-1, not UTF-8. A default `pd.read_csv` on a
   strict-UTF-8 host (e.g. Linux CI) raises `UnicodeDecodeError` before you
   produce a single row. `src/io.py` decodes it explicitly.
2. `baseline_3sigma.py`'s method has a blind spot: most gateways have **zero
   variance** in `reboot_cnt` over a 28-day window, so the standard deviation
   is 0, the z-score is undefined, and that gateway can never be flagged on
   that metric however badly it fails. How many depends on when you look —
   45% at the start of the history, rising to **69.8% across the scored
   window** (68.8–70.9% at the eight scored Mondays). It is specific to
   `reboot_cnt`: the other two metrics sit at 1.5%. Reproduce with
   `python scripts/zero_variance_check.py`.

Full reasoning in `DECISIONS.md` and `REPORT.md`.
