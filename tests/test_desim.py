import numpy as np

from qcom.desim import DarkStoreSim, SimConfig
from qcom.scenarios import provision, tier2_config, metro_config


def test_sim_runs_and_delivers_orders():
    cfg = provision(tier2_config(340, batch_target=1))
    res = DarkStoreSim(cfg, seed=1).run(replications=3)
    assert res.orders_delivered > 0
    assert 0.0 <= res.sla_breach_rate <= 1.0
    assert 0.0 <= res.rider_utilization <= 1.0


def test_arrivals_scale_with_orders_per_day():
    low = provision(tier2_config(340))
    high = provision(tier2_config(700))
    rl = DarkStoreSim(low, seed=2).run(replications=3)
    rh = DarkStoreSim(high, seed=2).run(replications=3)
    assert rh.orders_delivered > rl.orders_delivered


def test_reproducible_with_same_seed():
    cfg = provision(tier2_config(340))
    a = DarkStoreSim(cfg, seed=7).run(replications=2)
    b = DarkStoreSim(cfg, seed=7).run(replications=2)
    assert a.orders_delivered == b.orders_delivered
    assert a.mean_delivery_min == b.mean_delivery_min


def test_batching_reduces_rider_cost_per_order():
    # Same density, more batching -> fewer trips per order -> lower rider cost.
    b1 = provision(tier2_config(520, batch_target=1))
    b2 = provision(tier2_config(520, batch_target=2))
    r1 = DarkStoreSim(b1, seed=3).run(replications=4)
    r2 = DarkStoreSim(b2, seed=3).run(replications=4)
    assert r2.rider_cost_per_order < r1.rider_cost_per_order


def test_does_not_explode_on_batching():
    # Regression: batched dispatch once self-rescheduled FLUSH events forever.
    cfg = provision(tier2_config(340, batch_target=2))
    res = DarkStoreSim(cfg, seed=3).run(replications=3)
    assert res.orders_delivered > 0


def test_thinning_respects_operating_horizon():
    cfg = provision(tier2_config(340))
    sim = DarkStoreSim(cfg, seed=1)
    rng = np.random.default_rng(0)
    times = sim._generate_arrivals(rng)
    assert all(0 <= t < cfg.open_hours * 60 for t in times)
