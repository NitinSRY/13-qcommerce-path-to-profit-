from qcom.costs import CostModel, calibrate_fixed_cost


def test_fixed_cost_per_order_falls_with_volume():
    cm = CostModel(fixed_cost_per_day=15000.0)
    assert cm.fixed_cost_per_order(300) > cm.fixed_cost_per_order(1500)


def test_rider_cost_falls_with_batching():
    cm = CostModel()
    assert cm.rider_cost_per_order(1) > cm.rider_cost_per_order(2) > cm.rider_cost_per_order(3)


def test_contribution_higher_at_higher_density():
    cm = CostModel(fixed_cost_per_day=15000.0)
    low = cm.contribution_per_order(300, aov=560)
    high = cm.contribution_per_order(900, aov=560)
    assert high > low


def test_economics_breakdown_consistent():
    cm = CostModel()
    e = cm.economics(500, aov=600, batching=2, ad_take=0.03)
    assert abs(e.revenue - (e.revenue_product + e.revenue_ads)) < 1e-9
    assert abs(e.contribution - (e.revenue - e.cost)) < 1e-9


def test_calibrate_fixed_reproduces_reachable_target():
    # The closed-form fixed-cost calibration must reproduce any target that is
    # reachable with a non-negative fixed cost (i.e. at or below the contribution
    # before fixed cost). We derive such a target so the test is magnitude-robust.
    base = CostModel()
    contribution_without_fixed = base.with_fixed(0.0).contribution_per_order(1500, aov=709)
    target = contribution_without_fixed - 30.0  # needs a positive fixed cost
    cal = calibrate_fixed_cost(base, target, orders_per_day=1500, aov=709)
    assert cal.fixed_cost_per_day > 0
    assert abs(cal.contribution_per_order(1500, aov=709) - target) < 1e-6


def test_ad_take_override_increases_revenue():
    cm = CostModel()
    no_ad = cm.economics(500, aov=600, ad_take=0.0).revenue
    with_ad = cm.economics(500, aov=600, ad_take=0.04).revenue
    assert with_ad > no_ad
