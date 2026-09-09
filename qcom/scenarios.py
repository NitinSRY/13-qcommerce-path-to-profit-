"""Market regimes, roster provisioning, and the integrated twin economics.

Ties the three model layers together:

  * `provision` sizes the picker and rider rosters to the *evening peak* (with a
    minimum-staffing floor), which is how real operators staff. The floor is the
    structural source of the tier-2 hole: a sparse store still needs a minimum
    crew that sits idle off-peak, so its fixed cost is spread over too few orders.
  * `run_twin` runs the discrete-event simulation, then feeds the *realized*
    per-order rider and picking cost into the contribution-margin model, so the
    unit economics reflect the actual queueing and routing, not an average.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from qcom.costs import CostModel, OrderEconomics
from qcom.demand import DemandModel
from qcom.desim import DEFAULT_HOURLY_WEIGHTS, DarkStoreSim, SimConfig, SimResult, real_hourly_weights
from qcom.geo import GridCity


@dataclass
class TwinResult:
    """Operational + economic outcome of one configuration."""

    sim: SimResult
    econ: OrderEconomics
    n_pickers: int
    n_riders: int

    @property
    def contribution(self) -> float:
        return self.econ.contribution

    def as_dict(self) -> dict:
        d = {"n_pickers": self.n_pickers, "n_riders": self.n_riders}
        d.update({f"sim_{k}": v for k, v in self.sim.as_dict().items()})
        d.update({f"econ_{k}": v for k, v in self.econ.as_dict().items()})
        d["contribution"] = self.contribution
        return d


def _peak_per_min(orders_per_day: float, open_hours: float, weights=None) -> float:
    w = DEFAULT_HOURLY_WEIGHTS if weights is None else np.asarray(weights, dtype=float)
    hour_len = open_hours * 60.0 / len(w)
    peak_hour_orders = orders_per_day * w.max() / w.sum()
    return peak_hour_orders / hour_len


def provision(
    cfg: SimConfig,
    target_peak_util: float = 0.82,
    min_pickers: int = 2,
    min_riders: int = 4,
) -> SimConfig:
    """Size pickers and riders to the peak with a minimum-staffing floor.

    Picker service: one picker clears 1/mean_pick orders per minute.
    Rider service: a single trip (out + back + handover) at the configured speed;
    batching divides the effective trip rate per order by the batch size.
    """
    peak = _peak_per_min(cfg.orders_per_day, cfg.open_hours, cfg.weights())

    pick_rate_per_picker = 1.0 / cfg.mean_pick_min  # orders/min/picker
    n_pickers = max(min_pickers, math.ceil(peak / (pick_rate_per_picker * target_peak_util)))

    speed_km_per_min = cfg.rider_speed_kmph / 60.0
    single_trip_min = 2.0 * cfg.mean_drop_km / speed_km_per_min + cfg.handover_min
    # With batching, one trip serves up to batch_target drops; per-order trip time
    # is the multi-drop trip amortised over the batch (return leg shared).
    b = max(1, cfg.batch_target)
    per_order_trip_min = single_trip_min / b + (b - 1) * cfg.handover_min / b
    rider_throughput_per_min = 1.0 / per_order_trip_min
    n_riders = max(min_riders, math.ceil(peak / (rider_throughput_per_min * target_peak_util)))

    return replace(cfg, n_pickers=n_pickers, n_riders=n_riders)


def run_twin(
    cfg: SimConfig,
    cost: CostModel,
    aov: float,
    ad_take: float = 0.0,
    replications: int = 20,
    seed: int = 0,
    auto_provision: bool = True,
) -> TwinResult:
    """Run the discrete-event store, then price its realized operations."""
    if auto_provision:
        cfg = provision(cfg)
    sim = DarkStoreSim(cfg, seed=seed).run(replications=replications)
    econ = cost.economics(
        orders_per_day=sim.orders_delivered,
        aov=aov,
        batching=cfg.batch_target,
        ad_take=ad_take,
        rider_cost_per_order=sim.rider_cost_per_order,
        picking_cost_per_order=sim.picking_cost_per_order,
    )
    return TwinResult(sim=sim, econ=econ, n_pickers=cfg.n_pickers, n_riders=cfg.n_riders)


# ---- canonical market regimes (calibration-grade defaults) ----

def metro_config(orders_per_day: float = 1500.0) -> SimConfig:
    """A dense metro store: short drops, fast riders, high volume."""
    return SimConfig(
        orders_per_day=orders_per_day,
        mean_drop_km=0.9,
        rider_speed_kmph=22.0,
        mean_pick_min=2.6,
        handover_min=1.5,
        sla_min=15.0,
    )


def tier2_config(orders_per_day: float = 340.0, batch_target: int = 1) -> SimConfig:
    """A sparse tier-2 store: longer drops, slower roads, low volume."""
    return SimConfig(
        orders_per_day=orders_per_day,
        mean_drop_km=1.7,
        rider_speed_kmph=18.0,
        mean_pick_min=2.8,
        handover_min=2.0,
        batch_target=batch_target,
        sla_min=15.0,
    )


# ---- real-geography regimes (demand + drop distances from OSM, timing from real orders) ----

# Each real city: the committed OSM density grid, its real centre, cell size and a
# real population anchor for the modelled catchment area (see data/geo/README.md).
# orders_per_person_day encodes real q-commerce ADOPTION, which is far higher in the
# metros than in tier-2 cities (a documented penetration gap, not a modelling choice
# for its own sake). The spatial structure - where demand sits, how far the drops
# are, what a store can cover - comes entirely from the real OSM density grid.
REAL_CITIES = {
    "bengaluru": dict(
        csv="data/geo/bengaluru_density.csv",
        center=(12.9716, 77.5946), cell_km=0.9, population=900_000,
        orders_per_person_day=0.012, rider_speed_kmph=22.0, mean_pick_min=2.6,
        handover_min=1.5, label="metro",
    ),
    "lucknow": dict(
        csv="data/geo/lucknow_density.csv",
        center=(26.8467, 80.9462), cell_km=0.9, population=500_000,
        orders_per_person_day=0.005, rider_speed_kmph=18.0, mean_pick_min=2.8,
        handover_min=2.0, label="tier-2",
    ),
}


def real_city_demand(
    name: str,
    orders_per_person_day: float | None = None,
    beta: float = 1.8,
    max_serve_km: float = 1.8,
) -> dict:
    """Derive a store's order volume and mean drop distance from real geography.

    Loads the real OSM demand grid, places one dark store at the densest cell (where
    operators actually put them), and runs the gravity catchment to get the orders
    per day it would capture and the demand-weighted mean drop distance. Both come
    from the real city, not from a hand-set constant.
    """
    cfg = REAL_CITIES[name]
    if orders_per_person_day is None:
        orders_per_person_day = cfg["orders_per_person_day"]
    city = GridCity.from_density_csv(
        cfg["csv"], center=cfg["center"], cell_km=cfg["cell_km"], population=cfg["population"]
    )
    dm = DemandModel(
        city, orders_per_person_day=orders_per_person_day, beta=beta, max_serve_km=max_serve_km
    )
    # Store at the densest cell.
    dens = city.density
    ij = tuple(int(v) for v in np.unravel_index(int(dens.argmax()), dens.shape))
    store_cells = [ij]

    orders_per_day = float(dm.store_order_rates(store_cells)[0])
    probs = dm.capture_probabilities(store_cells)[:, 0]
    dist = dm.store_cell_distances(store_cells)[:, 0]
    pop = city.cell_population().reshape(-1)
    captured = probs * pop * orders_per_person_day
    mean_drop_km = float((captured * dist).sum() / captured.sum()) if captured.sum() > 0 else 0.0
    covered = dm.covered_demand_fraction(store_cells)
    return {
        "city": city, "store_cell": ij, "orders_per_day": orders_per_day,
        "mean_drop_km": mean_drop_km, "covered_fraction": covered, "label": cfg["label"],
    }


def real_city_config(
    name: str,
    batch_target: int = 1,
    use_real_timing: bool = True,
    **demand_kwargs,
) -> SimConfig:
    """A SimConfig whose demand volume, drop distance and (optionally) intraday
    arrival shape all come from real data for a real city."""
    d = real_city_demand(name, **demand_kwargs)
    cfg = REAL_CITIES[name]
    weights = real_hourly_weights() if use_real_timing else DEFAULT_HOURLY_WEIGHTS
    return SimConfig(
        orders_per_day=d["orders_per_day"],
        mean_drop_km=d["mean_drop_km"],
        rider_speed_kmph=cfg["rider_speed_kmph"],
        mean_pick_min=cfg["mean_pick_min"],
        handover_min=cfg["handover_min"],
        batch_target=batch_target,
        sla_min=15.0,
        hourly_weights=weights,
    )


def real_city_comparison(
    cost: CostModel,
    aov: float = 430.0,
    ad_take: float = 0.04,
    batch_target: int = 2,
    replications: int = 12,
    seed: int = 7,
) -> list[dict]:
    """Run the twin on each real city's geography and return the economics.

    Demand volume, drop distances and the intraday arrival shape all come from real
    data; the contribution gap between the metro and the tier-2 city is therefore an
    output of real geography, not an assumption.
    """
    rows = []
    for name, cfg in REAL_CITIES.items():
        d = real_city_demand(name)
        sc = real_city_config(name, batch_target=batch_target)
        tw = run_twin(sc, cost, aov=aov, ad_take=ad_take, replications=replications, seed=seed)
        rows.append({
            "city": name,
            "label": cfg["label"],
            "orders_per_day": round(d["orders_per_day"], 0),
            "mean_drop_km": round(d["mean_drop_km"], 2),
            "covered_fraction": round(d["covered_fraction"], 3),
            "n_riders": tw.n_riders,
            "n_pickers": tw.n_pickers,
            "rider_utilization": round(tw.sim.rider_utilization, 3),
            "contribution_per_order": round(tw.contribution, 2),
        })
    return rows
