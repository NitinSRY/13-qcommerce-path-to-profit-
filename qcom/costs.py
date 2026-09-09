"""Per-order unit economics and the contribution-margin model.

Contribution margin per order:

    margin = AOV * (product_take + ad_take)
             - packaging
             - rider_cost_per_order        (variable, falls with batching)
             - picking_cost_per_order      (semi-fixed: provisioned pickers / orders)
             - fixed_cost_per_order        (rent + overhead, fully fixed / orders)

The structural point the whole project rests on: rent, the picking roster and
rider availability are provisioned for *capacity*, not per order. Below a density
threshold those fixed costs are spread over too few orders and each order carries
idle capacity. The metro hides this with volume; tier-2 cannot. The model makes
that mechanism explicit and is calibrated so a dense regime reproduces a
published metro loss-per-order before we trust any tier-2 extrapolation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class OrderEconomics:
    """A full per-order P&L breakdown (all figures in INR per order)."""

    aov: float
    revenue_product: float
    revenue_ads: float
    packaging: float
    rider: float
    picking: float
    fixed: float

    @property
    def revenue(self) -> float:
        return self.revenue_product + self.revenue_ads

    @property
    def variable_cost(self) -> float:
        return self.packaging + self.rider

    @property
    def cost(self) -> float:
        return self.packaging + self.rider + self.picking + self.fixed

    @property
    def contribution(self) -> float:
        return self.revenue - self.cost

    def as_dict(self) -> dict[str, float]:
        return {
            "aov": self.aov,
            "revenue_product": self.revenue_product,
            "revenue_ads": self.revenue_ads,
            "packaging": self.packaging,
            "rider": self.rider,
            "picking": self.picking,
            "fixed": self.fixed,
            "revenue": self.revenue,
            "cost": self.cost,
            "contribution": self.contribution,
        }


@dataclass
class CostModel:
    """Parametric per-order economics, defensible against FY26 anchors.

    Defaults are calibration-grade for an Indian metro dark store. The free
    parameter that calibration adjusts is `fixed_cost_per_day` (rent + overhead),
    which is the genuinely hard-to-observe quantity.
    """

    # Net merchandise margin kept per rupee of AOV after cost of goods and
    # discounts. Grocery is a low-margin category, so q-commerce contribution
    # take is mid-single-digits, not the headline retail gross margin.
    product_take: float = 0.05
    ad_take: float = 0.0                # ad revenue as a fraction of AOV
    packaging_per_order: float = 11.0   # bag + handling per order
    rider_cost_per_trip: float = 42.0   # rider payout for one dispatch trip
    extra_stop_fraction: float = 0.35   # marginal cost of a 2nd drop on a batched trip
    picker_wage_per_day: float = 750.0  # one picker's fully-loaded daily wage
    picker_throughput_per_day: float = 320.0  # orders one picker can pick per day
    fixed_cost_per_day: float = 17000.0  # rent + utilities + store manager + overhead

    def rider_cost_per_order(self, batching: float) -> float:
        """Rider payout per order under a given average batch size.

        A batch of `b` orders shares one base trip; each extra drop adds a
        fraction of the trip cost. So per-order rider cost falls with b but not
        to zero, capturing the real density-vs-cost-per-drop curve.
        """
        b = max(1.0, batching)
        trip_cost = self.rider_cost_per_trip * (1.0 + self.extra_stop_fraction * (b - 1.0))
        return trip_cost / b

    def picking_cost_per_order(self, orders_per_day: float, picker_count: int | None) -> float:
        """Per-order picking cost given a provisioned picker roster.

        If picker_count is None we provision just enough pickers for the load
        (ceil(orders / throughput), min 1). The roster is paid whole days
        regardless of orders, so per-order picking cost rises as orders fall.
        """
        if orders_per_day <= 0:
            return float("inf")
        if picker_count is None:
            import math

            picker_count = max(1, math.ceil(orders_per_day / self.picker_throughput_per_day))
        return picker_count * self.picker_wage_per_day / orders_per_day

    def fixed_cost_per_order(self, orders_per_day: float) -> float:
        if orders_per_day <= 0:
            return float("inf")
        return self.fixed_cost_per_day / orders_per_day

    def economics(
        self,
        orders_per_day: float,
        aov: float,
        batching: float = 1.0,
        ad_take: float | None = None,
        picker_count: int | None = None,
        rider_cost_per_order: float | None = None,
        picking_cost_per_order: float | None = None,
    ) -> OrderEconomics:
        """Full per-order P&L.

        `rider_cost_per_order` and `picking_cost_per_order` let the discrete-event
        simulation inject the *realized* costs it measured from actual travel,
        idle time and queueing, instead of the parametric estimates. When None,
        the parametric estimates are used.
        """
        at = self.ad_take if ad_take is None else ad_take
        rider = (
            self.rider_cost_per_order(batching)
            if rider_cost_per_order is None
            else rider_cost_per_order
        )
        picking = (
            self.picking_cost_per_order(orders_per_day, picker_count)
            if picking_cost_per_order is None
            else picking_cost_per_order
        )
        return OrderEconomics(
            aov=aov,
            revenue_product=aov * self.product_take,
            revenue_ads=aov * at,
            packaging=self.packaging_per_order,
            rider=rider,
            picking=picking,
            fixed=self.fixed_cost_per_order(orders_per_day),
        )

    def contribution_per_order(self, orders_per_day: float, aov: float, **kw) -> float:
        return self.economics(orders_per_day, aov, **kw).contribution

    def with_fixed(self, fixed_cost_per_day: float) -> "CostModel":
        return replace(self, fixed_cost_per_day=fixed_cost_per_day)


def calibrate_fixed_cost(
    base: CostModel,
    target_loss_per_order: float,
    orders_per_day: float,
    aov: float,
    batching: float = 1.0,
    ad_take: float = 0.0,
) -> CostModel:
    """Solve for fixed_cost_per_day so the model reproduces a published loss/order.

    `target_loss_per_order` is signed: pass -3.02 to reproduce Blinkit's FY26
    -Rs 3.02/order. Since contribution is linear in fixed_cost_per_day, we invert
    it in closed form (no search needed).
    """
    # contribution = R - packaging - rider - picking - fixed/orders == target
    probe = base.with_fixed(0.0).economics(
        orders_per_day, aov, batching=batching, ad_take=ad_take
    )
    contribution_without_fixed = probe.contribution  # fixed component is 0 here
    # target = contribution_without_fixed - fixed_per_day / orders_per_day
    fixed_per_day = (contribution_without_fixed - target_loss_per_order) * orders_per_day
    return base.with_fixed(max(0.0, fixed_per_day))
