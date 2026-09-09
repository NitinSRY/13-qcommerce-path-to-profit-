"""The breakeven frontier and the cheapest path to profit.

The discrete-event twin is an expensive, noisy, black-box objective: contribution
margin as a function of the levers (order density, batching, AOV, ad take). To
find the *minimum-effort* lever combination that crosses contribution-positive
subject to an SLA constraint, we use derivative-free optimization, a from-scratch
Nelder-Mead simplex, with a penalty for the contribution and SLA constraints.

"Effort" weights each lever by how hard it is to move from the current baseline:
density needs demand generation, AOV needs merchandising / attach-rate work, ad
take needs a retail-media build-out. Minimising weighted effort subject to
contribution >= target and SLA <= cap yields the cheapest configuration that
makes entry rational, not just any profitable one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from qcom.costs import CostModel
from qcom.scenarios import tier2_config, run_twin


@dataclass
class Lever:
    name: str
    low: float
    high: float
    baseline: float
    effort_weight: float  # cost per unit of normalised movement from baseline


@dataclass
class FrontierConfig:
    levers: list[Lever]
    batch_target: int = 2
    target_margin: float = 0.0
    sla_cap: float = 0.35
    replications: int = 8
    seed: int = 3

    def baseline_vector(self) -> np.ndarray:
        return np.array([lv.baseline for lv in self.levers])

    def clip(self, x: np.ndarray) -> np.ndarray:
        return np.array([np.clip(x[i], lv.low, lv.high) for i, lv in enumerate(self.levers)])

    def effort(self, x: np.ndarray) -> float:
        e = 0.0
        for i, lv in enumerate(self.levers):
            span = lv.high - lv.low
            if span <= 0:
                continue
            move = max(0.0, (x[i] - lv.baseline)) / span  # only improving moves cost
            e += lv.effort_weight * move
        return e


def default_levers() -> list[Lever]:
    """A tier-2 lever space: density, AOV, ad take (batching handled separately).

    Each lever's floor is the tier-2 baseline: you grow demand, lift basket and
    build ad monetisation upward from where the lean store starts, you do not
    deliberately move them down. So every feasible point is reached by paid effort.
    """
    return [
        Lever("orders_per_day", 340.0, 900.0, 340.0, effort_weight=1.0),
        Lever("aov", 560.0, 720.0, 560.0, effort_weight=1.2),
        Lever("ad_take", 0.0, 0.05, 0.0, effort_weight=1.5),
    ]


def evaluate(cost: CostModel, fc: FrontierConfig, x: np.ndarray) -> dict:
    """Run the twin at lever vector x and return contribution + SLA."""
    opd, aov, ad = x
    cfg = tier2_config(orders_per_day=opd, batch_target=fc.batch_target)
    t = run_twin(cfg, cost, aov=aov, ad_take=ad, replications=fc.replications, seed=fc.seed)
    return {
        "contribution": t.contribution,
        "sla_breach": t.sim.sla_breach_rate,
        "twin": t,
    }


def _penalized(cost: CostModel, fc: FrontierConfig, x: np.ndarray) -> float:
    x = fc.clip(x)
    out = evaluate(cost, fc, x)
    penalty = 0.0
    # Hard penalty for failing the contribution target or the SLA cap.
    if out["contribution"] < fc.target_margin:
        penalty += 1000.0 + 50.0 * (fc.target_margin - out["contribution"])
    if out["sla_breach"] > fc.sla_cap:
        penalty += 1000.0 + 5000.0 * (out["sla_breach"] - fc.sla_cap)
    return fc.effort(x) + penalty


def nelder_mead(
    f,
    x0: np.ndarray,
    step: np.ndarray,
    max_iter: int = 60,
    alpha: float = 1.0,
    gamma: float = 2.0,
    rho: float = 0.5,
    sigma: float = 0.5,
) -> tuple[np.ndarray, float]:
    """A compact from-scratch Nelder-Mead simplex minimiser."""
    n = len(x0)
    simplex = [x0.copy()]
    for i in range(n):
        pt = x0.copy()
        pt[i] += step[i]
        simplex.append(pt)
    fvals = [f(p) for p in simplex]

    for _ in range(max_iter):
        order = np.argsort(fvals)
        simplex = [simplex[i] for i in order]
        fvals = [fvals[i] for i in order]
        centroid = np.mean(simplex[:-1], axis=0)

        # Reflection
        xr = centroid + alpha * (centroid - simplex[-1])
        fr = f(xr)
        if fvals[0] <= fr < fvals[-2]:
            simplex[-1], fvals[-1] = xr, fr
            continue
        # Expansion
        if fr < fvals[0]:
            xe = centroid + gamma * (xr - centroid)
            fe = f(xe)
            if fe < fr:
                simplex[-1], fvals[-1] = xe, fe
            else:
                simplex[-1], fvals[-1] = xr, fr
            continue
        # Contraction
        xc = centroid + rho * (simplex[-1] - centroid)
        fc_ = f(xc)
        if fc_ < fvals[-1]:
            simplex[-1], fvals[-1] = xc, fc_
            continue
        # Shrink
        for i in range(1, len(simplex)):
            simplex[i] = simplex[0] + sigma * (simplex[i] - simplex[0])
            fvals[i] = f(simplex[i])

    best = int(np.argmin(fvals))
    return simplex[best], fvals[best]


@dataclass
class FrontierResult:
    batch_target: int
    levers: dict[str, float]
    contribution: float
    sla_breach: float
    effort: float
    feasible: bool


def find_breakeven(cost: CostModel, fc: FrontierConfig) -> FrontierResult:
    """Find the cheapest lever combination that crosses the target margin."""
    x0 = fc.baseline_vector()
    step = np.array([(lv.high - lv.low) * 0.25 for lv in fc.levers])
    f = lambda x: _penalized(cost, fc, x)
    best_x, _ = nelder_mead(f, x0, step)
    best_x = fc.clip(best_x)
    out = evaluate(cost, fc, best_x)
    feasible = out["contribution"] >= fc.target_margin and out["sla_breach"] <= fc.sla_cap
    return FrontierResult(
        batch_target=fc.batch_target,
        levers={lv.name: float(best_x[i]) for i, lv in enumerate(fc.levers)},
        contribution=out["contribution"],
        sla_breach=out["sla_breach"],
        effort=fc.effort(best_x),
        feasible=feasible,
    )


def best_over_batching(
    cost: CostModel,
    target_margin: float = 0.0,
    sla_cap: float = 0.35,
    batch_options: tuple[int, ...] = (1, 2, 3),
    replications: int = 8,
) -> FrontierResult:
    """Search each batching level and return the lowest-effort feasible result."""
    best: FrontierResult | None = None
    for b in batch_options:
        fc = FrontierConfig(
            levers=default_levers(),
            batch_target=b,
            target_margin=target_margin,
            sla_cap=sla_cap,
            replications=replications,
        )
        res = find_breakeven(cost, fc)
        if not res.feasible:
            continue
        if best is None or res.effort < best.effort:
            best = res
    if best is None:
        # Nothing feasible: return the closest attempt at batch=2 for reporting.
        fc = FrontierConfig(default_levers(), batch_target=2, target_margin=target_margin,
                            sla_cap=sla_cap, replications=replications)
        best = find_breakeven(cost, fc)
    return best


def frontier_curve(
    cost: CostModel,
    densities: tuple[float, ...] = (340.0, 460.0, 580.0, 700.0, 820.0),
    batch_target: int = 2,
    aov: float = 600.0,
    ad_cap: float = 0.06,
    target_margin: float = 0.0,
    replications: int = 8,
) -> list[dict]:
    """The breakeven frontier: required ad-monetisation vs density.

    For each order density, bisect the ad take needed to reach the target margin
    at fixed batching and AOV. The curve is the density-vs-required-monetisation
    tradeoff: denser stores need less monetisation to break even, and below some
    density no feasible ad take closes the gap. This is the frontier the board
    reads to set the no-go density line.
    """
    rows = []
    for opd in densities:
        def contrib(ad: float) -> float:
            cfg = tier2_config(orders_per_day=opd, batch_target=batch_target)
            t = run_twin(cfg, cost, aov=aov, ad_take=ad, replications=replications, seed=3)
            return t.contribution

        lo, hi = 0.0, ad_cap
        c_hi = contrib(hi)
        if c_hi < target_margin:
            rows.append({"orders_per_day": opd, "required_ad_take": None,
                         "contribution_at_cap": c_hi, "feasible": False})
            continue
        # Bisect for the smallest ad take that meets the target.
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            if contrib(mid) >= target_margin:
                hi = mid
            else:
                lo = mid
        rows.append({"orders_per_day": opd, "required_ad_take": hi,
                     "contribution_at_cap": c_hi, "feasible": True})
    return rows


def aov_only_strawman(
    cost: CostModel,
    densities: tuple[float, ...] = (340.0, 520.0, 700.0),
    aov: float = 720.0,
    replications: int = 8,
) -> list[dict]:
    """The 'just copy the metro premium-AOV playbook' baseline.

    Hold batching at 1 and push AOV to its ceiling with no ad take; show it fails
    to close at low density because the binding constraint is density, not basket.
    """
    rows = []
    for opd in densities:
        cfg = tier2_config(orders_per_day=opd, batch_target=1)
        t = run_twin(cfg, cost, aov=aov, ad_take=0.0, replications=replications, seed=3)
        rows.append(
            {
                "orders_per_day": opd,
                "aov": aov,
                "contribution": t.contribution,
                "sla_breach": t.sim.sla_breach_rate,
            }
        )
    return rows
