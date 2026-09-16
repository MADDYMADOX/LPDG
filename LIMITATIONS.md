# What this cannot do, and what two more weeks would fix

## Known limitations

**The proxy label conflates meter problems with gateway problems.** A low
`meters_read/meters_expected` ratio is our stand-in for "this gateway needed
attention," but it can also reflect a meter-side issue (a swap in progress, a
customer refusing access) that no amount of gateway maintenance would fix.
We have no field in the given data that distinguishes these. Practically:
our reported precision (66-87% depending on threshold) is a *floor* on how
often the method points at a real gateway problem, not an exact number —
some of what we count as a "miss" or a "hit" may be mislabeled for reasons
outside the gateway network entirely.

**The meter-trend feature goes stale after the first scored week.**
`meter_read_success.csv` stops on 2026-01-26, before the scored window
(2026-02-02 onward) even starts. So for every one of the 8 scored weeks, the
"trailing meter ratio" input is the same frozen snapshot from late January —
it acts as a static long-run health prior ("was this gateway chronically
underperforming before the window began"), not a live, week-by-week signal,
for the actual submission. In the backtest, where fresh meter data *was*
available each week, this feature earns its 30% weight; in the real scored
window it contributes less than the backtest would suggest. This is disclosed
here rather than smoothed over in `REPORT.md`'s headline numbers.

**No evidence a visit fixes anything within the same week.** The cost model
(and the backtest) implicitly assumes that flagging a gateway this Monday and
visiting it this week resolves the problem. `field_visits.csv` shows a
median 9-day gap between a work order being requested and a technician
attending — often longer than the week the visit was "for." We have not
validated that our ranking, if acted on, would show up as a same-week
improvement in `meters_read`.

**The 15-visit cap limits how much any ranking method can achieve.** Across
the backtested weeks, an average of ~38 gateways had a genuinely bad week by
our proxy, against 15 available visit slots — so even a hypothetically
perfect ranker is capped near 40% recall. Our method recovers roughly
two-thirds of that ceiling (26% baseline -> 34% blended, against a ~40%
ceiling). The bigger lever for the ops manager may be visit capacity itself,
which is outside this challenge's scope but worth saying plainly.

**We re-pick gateways we picked last week, and cannot tell whether that is
waste.** 37 of the 105 consecutive-week slots in the submission are repeat
picks. Under the scorer's episode accounting, a repeat inside an episode we
already caught earns nothing and still costs €380 and one of the 15 slots. We
have no way to separate "still the same unfixed fault" from "a new episode"
with the data given, and our backtest scores weeks independently so it cannot
referee a cooldown rule either. Quantified rather than smoothed over; the
reasoning is in `DECISIONS.md` §5.

**One hardware model, one unit.** `GW-8800X` appears exactly once in
`gateway_master.csv`. Our per-gateway z-score approach doesn't need peers
(it compares each gateway to its own history), so this isn't a bug we found
evidence of — but it means we have no way to sanity-check whether that one
gateway's "normal" baseline is itself typical for its hardware class.

**Backtest sample is modest.** 21 weeks, no explicit seasonal modelling
(e.g., whether outdoor-mast gateways behave differently in winter). The
bootstrap CIs in `REPORT.md` describe uncertainty from resampling those 21
weeks; they do not capture uncertainty from, say, a hardware refresh or a
firmware rollout that hasn't happened yet in this data.

## What another two weeks would buy

1. **Visit outcomes fed back per gateway-week**, so "did the read ratio
   recover after this visit" becomes measurable. That is the missing input
   that turns the repeat-pick question above from a judgement call into a
   one-parameter decision (how many weeks to suppress a gateway for), and it
   is the single change that would move the most money. First, because
   everything else on this list is smaller.
2. **Time-gated use of `engineer_review_2026-02.xlsx`.** It's unusable for
   the first two scored weeks (leakage), but legitimately available from
   2026-02-16 onward — we did not integrate it at all, for consistency
   across weeks. A version that switches it on only where it's temporally
   valid would likely sharpen the later weeks.
3. **An uplift/causal check on the visit-lag data** — using the variation in
   `requested_on` -> `visited_on` gaps in `field_visits.csv` to estimate how
   much of a read-ratio recovery is actually attributable to a visit versus
   the problem resolving on its own, which would directly test the
   assumption the whole cost model rests on.
4. **A live weekly meter-feed**, instead of a frozen export, so the
   meter-trend term stays a real signal through the whole scored window
   rather than freezing after week 1.
5. **Formal hazard/survival modelling per gateway** in place of the 3-sigma
   heuristic, if a longer labeled history were available — the current
   method was chosen partly because ~20-26 weeks of data doesn't comfortably
   support anything more complex without overfitting risk.
