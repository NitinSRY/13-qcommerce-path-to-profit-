"""Calibrate the cost model so the dense regime reproduces a published loss/order.

The calibration proof: run the metro twin (discrete-event store at metro density),
take the realized rider and picking cost, then solve for the one free, hard-to-
observe parameter (the dark-store fixed cost per day) so the metro contribution
equals the published FY26 loss-per-order. Only after the dense regime matches the
real anchor do we trust the model's tier-2 extrapolation.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from qcom.costs import CostModel
from qcom.scenarios import metro_config, provision
from qcom.desim import DarkStoreSim


@dataclass
class Anchor:
    player: str
    loss_per_order: float
    aov: float


def load_anchors(path: str | Path) -> list[Anchor]:
    anchors: list[Anchor] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["loss_per_order_inr"] in ("", "NA"):
                continue
            anchors.append(
                Anchor(
                    player=row["player"],
                    loss_per_order=float(row["loss_per_order_inr"]),
                    aov=float(row["aov_inr"]),
                )
            )
    return anchors


def calibrate_to_metro(
    base: CostModel,
    target_loss_per_order: float,
    aov: float,
    orders_per_day: float = 1500.0,
    replications: int = 20,
    seed: int = 1,
) -> tuple[CostModel, dict]:
    """Solve fixed_cost_per_day from a metro twin run.

    Returns the calibrated CostModel and a diagnostics dict (the metro sim
    outputs + the reproduced contribution, which should equal the target).
    """
    cfg = provision(metro_config(orders_per_day))
    sim = DarkStoreSim(cfg, seed=seed).run(replications=replications)

    # contribution = revenue - packaging - rider - picking - fixed/orders
    probe = base.with_fixed(0.0).economics(
        orders_per_day=sim.orders_delivered,
        aov=aov,
        rider_cost_per_order=sim.rider_cost_per_order,
        picking_cost_per_order=sim.picking_cost_per_order,
    )
    contribution_without_fixed = probe.contribution
    fixed_per_day = (contribution_without_fixed - target_loss_per_order) * sim.orders_delivered
    calibrated = base.with_fixed(max(0.0, fixed_per_day))

    check = calibrated.economics(
        orders_per_day=sim.orders_delivered,
        aov=aov,
        rider_cost_per_order=sim.rider_cost_per_order,
        picking_cost_per_order=sim.picking_cost_per_order,
    )
    diag = {
        "orders_per_day": sim.orders_delivered,
        "sla_breach_rate": sim.sla_breach_rate,
        "rider_utilization": sim.rider_utilization,
        "picker_utilization": sim.picker_utilization,
        "rider_cost_per_order": sim.rider_cost_per_order,
        "picking_cost_per_order": sim.picking_cost_per_order,
        "fixed_cost_per_day": calibrated.fixed_cost_per_day,
        "target_loss_per_order": target_loss_per_order,
        "reproduced_contribution": check.contribution,
        "n_pickers": cfg.n_pickers,
        "n_riders": cfg.n_riders,
    }
    return calibrated, diag


DEFAULT_ANCHORS_PATH = Path(__file__).resolve().parent.parent / "data" / "qcom_financials_fy26.csv"
