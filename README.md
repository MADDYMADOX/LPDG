# LPDG Innovation Hub 2026 — Selection Challenge

Which 15 gateways to visit each week, and why. Part 2 track: **Data science**.

## Run it

One command, either way. Put the `data` folder exactly as provided at the
project root first (it's git-ignored, not shipped in this repo — see
`.gitignore`).

**Docker (no local Python needed):**

```
docker compose up --build
```

Writes `predictions.csv` to the project root and validates it as the last
build step (the container fails if validation fails).

**Or locally:**

```
pip install -r requirements.txt
python -m src.predict --data data --out predictions.csv
python validate_submission.py predictions.csv
```

Reproduce the backtest and charts behind `REPORT.md`:

```
python scripts/backtest.py      # writes scripts/backtest_results.csv
python scripts/make_charts.py   # writes report/figures/*.png
python -m pytest tests/ -q
```

## What this is

- `src/io.py` — loaders, each one validating its own assumptions about the
  file it reads instead of trusting it blindly (see the encoding bug below).
- `src/scoring.py` — the ranking method: a leak-free blend of a 3-sigma
  telemetry-anomaly signal and a lagged meter-read-success trend.
- `src/predict.py` — builds `predictions.csv` for the 8 scored weeks.
- `scripts/backtest.py` — the honest, leak-free historical backtest this
  method is justified by (21 weeks, 4 different definitions of "needs a
  visit," bootstrapped confidence intervals). Run with `python scripts/backtest.py`.
- `tests/` — a handful of tests, including regression tests for two real
  bugs found in this data (see below).
- `DECISIONS.md`, `LIMITATIONS.md`, `AI-USAGE.md`, `REPORT.md` — the
  required write-ups.

## Two things this data will do to you

1. `gateway_master.csv` is Latin-1, not UTF-8. A default `pd.read_csv` on a
   strict-UTF-8 host (e.g. Linux CI) raises `UnicodeDecodeError` before you
   produce a single row. `src/io.py` decodes it explicitly.
2. `baseline_3sigma.py`'s method has a blind spot: 53% of gateways have
   zero variance in `reboot_cnt` over any 28-day window, so `std=0` propagates
   to `NaN` and that gateway can never be flagged on that metric, however
   badly it fails. See `LIMITATIONS.md`.

Full reasoning in `DECISIONS.md` and `REPORT.md`.
