"""Run the full study and write the headline numbers to reports/results.json.

This is the reproducible driver behind docs/PERF_REPORT.md:

  1. Calibrate the cost model so the metro twin reproduces Blinkit's FY26
     loss-per-order (the calibration proof).
  2. The tier-2 fragility result: the lean store's contribution, SLA, and the
     dominant cost.
  3. The breakeven frontier: the cheapest lever mix that crosses to positive.
  4. The AOV-only strawman that fails on density.
  5. Sobol global sensitivity naming the binding constraint.
  6. Facility-location placement vs naive equal-spacing, with the LP bound.

Usage:
    python scripts/run_experiments.py --quick     # fast, fewer replications
    python scripts/run_experiments.py             # full run
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qcom.costs import CostModel
from qcom.calibrate import calibrate_to_metro, load_anchors, DEFAULT_ANCHORS_PATH
from qcom.scenarios import tier2_config, run_twin
from qcom.frontier import best_over_batching, aov_only_strawman
from qcom.sensitivity import run_sobol
from qcom.geo import GridCity
from qcom.place import FacilityLocator

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer replications / smaller Sobol")
    ap.add_argument("--out", default=str(REPORTS / "results.json"))
    args = ap.parse_args()

    reps = 8 if args.quick else 20
    sobol_n = 24 if args.quick else 64
    sobol_reps = 2 if args.quick else 3

    t0 = time.time()
    results: dict = {"meta": {}}

    # 1. Calibration to the published metro anchor (Blinkit FY26).
    anchors = load_anchors(DEFAULT_ANCHORS_PATH)
    blinkit = next(a for a in anchors if a.player == "Blinkit")
    cal, diag = calibrate_to_metro(
        CostModel(), target_loss_per_order=blinkit.loss_per_order, aov=blinkit.aov,
        replications=reps,
    )
    results["calibration"] = diag
    results["calibration"]["anchor_player"] = blinkit.player

    # Persist the calibrated cost model for instant Streamlit load.
    cal_json = {
        "product_take": cal.product_take,
        "packaging_per_order": cal.packaging_per_order,
        "rider_cost_per_trip": cal.rider_cost_per_trip,
        "picker_wage_per_day": cal.picker_wage_per_day,
        "fixed_cost_per_day": cal.fixed_cost_per_day,
        "diag": diag,
    }
    (ROOT / "app" / "calibration.json").write_text(json.dumps(cal_json, indent=2, default=str))

    # 2. Tier-2 fragility: the lean store at baseline.
    lean = run_twin(tier2_config(340, batch_target=1), cal, aov=560, replications=reps, seed=2)
    results["tier2_fragility"] = lean.as_dict()

    # 3. Breakeven frontier.
    front = best_over_batching(cal, target_margin=0.0, sla_cap=0.35, replications=reps)
    results["breakeven_frontier"] = {
        "batch_target": front.batch_target,
        "levers": front.levers,
        "contribution": front.contribution,
        "sla_breach": front.sla_breach,
        "effort": front.effort,
        "feasible": front.feasible,
    }

    # 4. AOV-only strawman.
    results["aov_only_strawman"] = aov_only_strawman(cal, replications=reps)

    # 5. Sobol sensitivity.
    sob = run_sobol(cal, n=sobol_n, replications=sobol_reps)
    results["sobol"] = sob.as_dict()
    results["sobol"]["ranked"] = sob.ranked()

    # 6. Facility location vs equal-spacing.
    city = GridCity.synthetic(n=14, cell_km=0.8)
    loc = FacilityLocator(city, service_km=2.0, candidate_stride=2)
    opt = loc.solve(n_stores=6, with_bound=True)
    naive = loc.equal_spacing(6)
    results["placement"] = {
        "n_stores": 6,
        "optimized_covered_fraction": opt.covered_fraction,
        "naive_covered_fraction": naive.covered_fraction,
        "lp_upper_bound": opt.lp_upper_bound,
        "optimality_gap": opt.optimality_gap,
        "optimized_cells": opt.store_cells,
    }

    results["meta"] = {
        "elapsed_sec": round(time.time() - t0, 1),
        "replications": reps,
        "sobol_n": sobol_n,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }

    REPORTS.mkdir(exist_ok=True)
    out = Path(args.out)
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"wrote {out} in {results['meta']['elapsed_sec']}s")
    print(f"  metro reproduced contribution = {diag['reproduced_contribution']:.2f} "
          f"(target {diag['target_loss_per_order']})")
    print(f"  tier-2 lean contribution      = {lean.contribution:.1f}/order, "
          f"SLA breach {lean.sim.sla_breach_rate:.1%}, rider util {lean.sim.rider_utilization:.0%}")
    print(f"  breakeven                     = {front.contribution:.1f}/order at "
          f"{front.levers} batch {front.batch_target}")
    print(f"  Sobol ST ranking              = {[(n, round(st,2)) for n,_,st in sob.ranked()]}")
    print(f"  placement covered             = {opt.covered_fraction:.1%} vs naive "
          f"{naive.covered_fraction:.1%}, gap to LP {opt.optimality_gap:.1%}")


if __name__ == "__main__":
    main()
