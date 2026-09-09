# Decisions

Five choices, what else was on the table, and why we didn't take it.

## 1. Part 2 track: Data science

**Chosen:** Data science — define what "needs a visit" means, test it honestly,
and turn the €380/€600 costs into an actual decision.

**Alternative considered:** Machine learning — train a model to beat
`baseline_3sigma.py` on cost.

**Why not:** The grading weights are 60% the chosen track, 25% judgement, 15%
explaining. The last two (40% of the grade) are identical no matter which
track we pick, and they are exactly what the data-science bullets ask for —
own the ambiguity, defend the threshold, report a range rather than a point
estimate. With ~500 candidates, the ML track will be the most crowded and the
easiest to get subtly wrong (leakage, overfitting to the weeks/gateways you
happened to test on) — the brief explicitly says it tests for that in the
live round. A transparent, leak-free, cost-justified scoring method is both
easier to defend live and, on the evidence in `REPORT.md`, already beats the
baseline by a comfortable margin without needing to be a trained model.

## 2. Definition of "needs a visit"

**Chosen:** `meters_read / meters_expected < 0.70` for a gateway in a given
week, from `meter_read_success.csv`.

**Alternatives considered and rejected:**

- **"Was field-visited historically" (`field_visits.csv`)** — rejected because
  it is not a label for "needed a visit," it is a label for "the current
  spreadsheet-and-gut-feel process chose to look here." That process found no
  fault on 60.7% of its own visits (390/642), so training or validating
  against it would just reward learning to reproduce a process the brief
  itself says is bad (selection bias: we would only ever see labels for
  gateways someone already suspected).
- **Engineer's `Kategorie` (`engineer_review_2026-02.xlsx`)** — rejected as a
  general-purpose label. It covers only 120/332 gateways (36%), was recorded
  by one reviewer on one day, and — more importantly — is dated 2026-02-15,
  which is *after* the first two scored Mondays (2026-02-02, 2026-02-09).
  Using it as ground truth (or a feature) for those two weeks would be
  leaking roughly a week of the future into the prediction.
- **A stricter/looser read-ratio cutoff** — we did not pick 70% by tuning it
  against results; we checked 50/60/70/80% and the result holds at all four
  (see `report/figures/precision_by_threshold.png`), which matters more than
  the exact number. 70% is reported as the headline because it sits in the
  middle of a range we'd defend to an ops manager as "a meaningfully
  degraded week, not a rounding error."

**What this test cannot tell you:** a low read-ratio can be caused by the
meter, not the gateway (a swapped meter, a customer access problem). We do
not have a way to separate these with the data given — see `LIMITATIONS.md`.

## 3. Scoring method: a transparent blend, not a trained model

**Chosen:** `blended_score = 0.7 * normalized(3-sigma flagged hours) +
0.3 * (1 - trailing 2-week meter-read ratio)`, both computed strictly before
the target Monday (`src/scoring.py`).

**Alternative considered:** train a classifier/regressor (logistic
regression, gradient boosting) on the ~21-26 historical weeks with labels.

**Why not:** We have on the order of 300 gateways × ~20 usable weeks — not
nothing, but thin for a model whose main job in the live round is surviving
scrutiny ("make your model better on the month it hasn't seen," or in our
case, defend why it still works). A two-term weighted blend has zero
hyperparameters to overfit, is fully explainable in one sentence, and the
backtest (`scripts/backtest.py`) shows it already beats the baseline by 21/21
weeks at four different thresholds. We would rather hand over something
boring and correct than something impressive and fragile — this is also
explicitly what the brief rewards ("fewer clever parts rather than more").

## 4. Blend weight (70/30), chosen once, not tuned per threshold

**Chosen:** Fix 70% telemetry / 30% meter-trend once, then check it holds
across four different definitions of "needs a visit."

**Alternative considered:** Grid-search the weight (and the 28-day/7-day
windows, and SIGMA) to maximize backtested precision.

**Why not:** With only 21 backtested weeks, searching a large parameter grid
against the same 21 weeks and then reporting the best result is exactly the
kind of soft leakage the brief warns about — you'd be fitting to the
backtest, not to the phenomenon. We picked one reasonable weighting
(telemetry as the primary, always-live signal; meter trend as a secondary
correction) and spent the search budget on checking robustness across
*different ground-truth definitions* instead of squeezing the last point of
precision out of one definition.

## 5. Data-quality handling: fail loudly, per file, never guess once for all

**Chosen:** Each loader in `src/io.py` validates its own assumptions about
its file (encoding, required columns, no duplicate gateway IDs, no negative
counts) and raises `DataQualityError` rather than continuing.

**Alternative considered:** wrap the whole read in `try/except` and either
skip bad rows or fall back to a default encoding for all CSVs.

**Why not:** `gateway_master.csv` is Latin-1; `field_visits.csv` is UTF-8. A
single blanket "read everything as Latin-1" fix would have silently
worked for one file and silently mis-decoded the other on some inputs. A
`predictions.csv` produced from a partially-wrong read is worse than a run
that stops and tells you why — this is the philosophy the brief itself states
for the data-engineering track, and we think it should apply to any track
that touches this data, not just that one.
