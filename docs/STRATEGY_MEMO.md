# Strategy memo: should we enter tier-2 quick commerce, and how?

**To:** Investment committee / market-entry board
**Re:** Tier-2 quick-commerce entry, go/no-go and configuration
**Basis:** the path-to-profit digital twin, calibrated to FY26 financials

## The one-line takeaway

A lean tier-2 store loses about **Rs 65 per order**, and the cause is density, not
basket size. Rider idle time dominates at 340 orders/day. Two-order batching plus a
4% ad take crosses to breakeven at about 790 orders/day with the basket unchanged.
Copying the metro premium-basket playbook never closes here. Enter above the density
line with this configuration; below it, do not.

## What the model is

A spatial dark-store digital twin that simulates one store from demand to dispatch
to margin: a gravity demand catchment, a discrete-event store (evening-peak Poisson
arrivals, a picking queue, rider dispatch with batching over the road graph), and a
per-order contribution-margin model. It is calibrated so the dense metro regime
reproduces the published FY26 loss-per-order (Blinkit -Rs 3.02/order) before any
tier-2 number is trusted.

## What it found

1. **The tier-2 hole is structural.** At 340 orders/day the fixed cost (rent and
   roster) is Rs 50.6 of the per-order cost, because it is spread over too few
   orders. Riders sit about 60% idle. Contribution is -Rs 64.9/order.

2. **The binding constraint is density and batching, not basket.** A Sobol
   sensitivity analysis attributes about 78% of the margin variance to order
   density and rider batching, and only about 8% to basket size.

3. **The cheapest path to profit.** The minimum-effort lever mix that reaches
   breakeven is two-order batching plus a 4.3% ad take plus growing density to about
   790 orders/day, with the basket left at Rs 560. Denser stores need less
   monetisation to break even.

4. **The metro playbook fails here.** Pushing the basket to Rs 720 with no batching
   stays at -Rs 29/order even at 700 orders/day. Targeted density-and-batching beats
   the blanket premium-basket strategy.

5. **Placement matters.** The facility-location optimizer covers 40.2% of demand
   with six stores, versus 35.7% for naive equal-spacing, and matches the LP upper
   bound (provably optimal on this grid).

## The decision

- **Go** in tier-2 catchments where the addressable density supports growth past the
  breakeven line (about 790 orders/day per store), and enter with two-order batching
  and a retail-media (ad) build-out from day one, not as an afterthought.
- **No-go** below about 580 orders/day of reachable density, where no ad take within
  a realistic cap closes the gap. Do not enter and hope the basket will save it.
- **Do not** lead with a premium-basket strategy in tier-2. It does not address the
  binding constraint.

## What would change the call

The conclusion is robust to the calibration because it is anchored to a published
loss-per-order, but it should be re-parameterised with the operator's own rent,
rider-wage and demand data before committing capital. The twin is built to be
re-run with those inputs.
