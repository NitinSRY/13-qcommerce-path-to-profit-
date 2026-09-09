# Performance and results report

All numbers below are reproduced by `python scripts/run_experiments.py` and saved
to `reports/results.json`. Figures are produced by `python scripts/make_figures.py`.

## Method and machine

- Machine: Apple M-series laptop, macOS, Python 3.13 (CI also runs 3.10 to 3.12).
- Simulation: 20 replications per configuration (a replication is one operating day
  of 16 hours). The Sobol analysis uses Saltelli sample size N = 64, so the twin is
  evaluated 64 x (4 + 2) = 384 times, each at 3 replications.
- Currency: Indian rupees (Rs). Contribution is per delivered order.
- Run time: about 145 seconds for the full study on the laptop above.

## 1. Calibration proof

The cost model solves for the dark-store fixed cost per day so the dense metro
regime reproduces Blinkit's published FY26 loss-per-order.

| Quantity | Value |
| --- | --- |
| Metro density (provisioned to peak) | 1,511 orders/day, 10 pickers, 24 riders |
| Metro SLA breach (delivery > 15 min) | 0.0% |
| Metro rider utilisation | 42% |
| Realised rider cost / order (metro) | Rs 11.1 |
| Realised picking cost / order (metro) | Rs 5.0 |
| Solved dark-store fixed cost | Rs 17,217/day |
| Reproduced contribution | **-Rs 3.02/order** (target -Rs 3.02, Blinkit FY26) |

The solved fixed cost (about Rs 17k/day) is a realistic dark-store daily cost of
rent, utilities, a store manager and overhead, which is the check that the
calibration is physically sensible rather than a curve-fit.

## 2. Tier-2 fragility (the headline)

The lean tier-2 store: 340 orders/day, single-order dispatch, Rs 560 basket, same
calibrated cost model.

| Quantity | Value |
| --- | --- |
| Contribution | **-Rs 64.9/order** |
| SLA breach | 11.4% |
| Mean delivery | 10.9 min (p90 15.3 min) |
| Rider utilisation | 40% (riders sit about 60% idle) |
| Fixed cost / order | Rs 50.6 |
| Rider cost / order | Rs 24.7 |
| Picking cost / order | Rs 6.6 |
| Merchandise margin / order | Rs 28.0 |

The cost split is the mechanism: fixed cost is the single largest line at Rs 50.6
per order, because the rent and roster are spread over only 340 orders. Density,
not basket, is the binding constraint.

## 3. Breakeven frontier

The derivative-free search returns the minimum-effort lever mix that crosses
contribution-positive subject to the SLA cap.

| Lever | Baseline (lean) | Breakeven |
| --- | --- | --- |
| Order density | 340/day | ~790/day |
| Rider batching | 1 | 2 |
| Ad take | 0% | 4.3% |
| AOV (basket) | Rs 560 | Rs 560 (unchanged) |
| Contribution | -Rs 64.9 | ~Rs 0 (breakeven) |

The optimizer leaves the basket at baseline and reaches breakeven through density,
batching and ad monetisation. The frontier curve (`reports/frontier.png`) shows the
required ad take falling as density rises, and that below about 580 orders/day no ad
take within a 6% cap closes the gap, which is the no-go density line for the board.

## 4. Targeted beats blanket (the AOV-only strawman)

Copying the metro premium-AOV playbook: push the basket to Rs 720, no batching.

| Density | AOV-only contribution |
| --- | --- |
| 340/day | -Rs 56.9 |
| 520/day | -Rs 39.0 |
| 700/day | -Rs 29.4 |

It never closes, even at double the lean density, because the binding constraint is
density and dispatch, not basket size.

## 5. Sobol global sensitivity (the binding constraint)

Variance attribution of contribution margin over the lever space (density 300 to
900, batching 1 to 3, AOV 520 to 720, ad take 0 to 5%).

| Lever | First-order S1 | Total ST |
| --- | --- | --- |
| Order density | 0.48 | **0.64** |
| Ad take | 0.26 | 0.35 |
| Rider batching | 0.07 | 0.14 |
| AOV (basket) | 0.01 | **0.08** |

Order density and batching together account for about 78% of the margin variance,
while basket size accounts for about 8%. This is the measured form of the
recommendation: it is density and batching, not basket. See
`reports/sobol_tornado.png`.

## 6. Facility-location placement

Six dark stores on a 14x14 demand grid, 2 km service radius.

| Method | Demand covered |
| --- | --- |
| Optimizer (greedy + local search) | **40.2%** |
| Naive equal-spacing | 35.7% |
| LP relaxation upper bound | 40.2% (gap 0.0%) |

The optimizer matches the LP upper bound on this instance, so its placement is
provably optimal here, and it beats naive equal-spacing by about 4.5 points of
covered demand. See `reports/placement_map.png`.

## 7. Real-geography validation (OpenStreetMap + real order timing)

Reproduce with `make real` (`python -m qcom.cli real`). Instead of a synthetic
density grid, the twin runs on the real spatial structure of two cities. The demand
surface is the real location of shops and amenities from OpenStreetMap (Overpass):
~10,800 POIs in Bengaluru, ~520 in Lucknow. The intraday arrival shape is fitted to
real order timestamps (25,900 orders, UCI Online Retail). A store is placed at the
densest real cell; its order volume and mean drop distance come from the gravity
catchment over the real grid.

| city (real geography) | orders/day | mean drop km | riders | contribution/order |
| --- | --- | --- | --- | --- |
| Bengaluru (metro) | 1,247 | 0.99 | 17 | **-Rs 2.11** |
| Lucknow (tier-2) | 350 | 0.39 | 4 | **-Rs 38.76** |

- The metro store on real Bengaluru geography lands at -Rs 2.11/order, independently
  close to the real Blinkit FY26 -Rs 3.02 the twin was not fit to at the city level.
- The tier-2 store is Rs 36.6/order worse, driven by 3.6x lower real order density.
  This reproduces the "density is the binding constraint" finding from real geography.
- Real structure detail: Bengaluru is polycentric (POIs spread over many cells);
  Lucknow is monocentric (one dense core, 67% of cells near-empty). The tier-2 core
  gives shorter drops (0.39 km) but far too few orders to cover the fixed crew.

Honest scope: `orders_per_person_day` encodes the real metro-vs-tier-2 adoption gap
(a documented penetration difference, higher in metros); everything spatial - where
demand sits, drop distances, coverage - comes from the OSM grid. The order-timing
curve is a real online-retail shape (daytime-peaked), not q-commerce specific; the
synthetic bimodal profile stays available for comparison.

## Reproducibility and caveats

- The simulation is seeded; the same seed and replication count reproduce the same
  numbers across machines.
- Late decimals move slightly with replication count because the simulator is
  stochastic; the qualitative findings (the sign of tier-2 contribution, the lever
  ranking, the frontier shape) are stable.
- Demand is calibrated to public density and published GMV anchors, not an
  operator's private order log. The model is one city's structure, not a full
  network. These limits are stated in the README.
