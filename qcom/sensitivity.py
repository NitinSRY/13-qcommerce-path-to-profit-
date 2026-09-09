"""Sobol global sensitivity analysis, implemented from scratch.

A one-at-a-time tornado only probes the model near one point. Sobol indices
decompose the *variance* of the output (contribution margin) into the fraction
attributable to each lever and its interactions, across the whole input space.
That is what lets us claim, honestly, which levers actually move profitability,
rather than guessing.

We use Saltelli sampling and the Jansen estimators:

    S_i  (first order) measures the variance removed if lever i were fixed.
    ST_i (total order)  measures the variance left if all but lever i were fixed,
                        so it captures interactions.

If density and batching carry the large indices and AOV a small one, the
recommendation "it is density and batching, not basket" is a measured attribution.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qcom.costs import CostModel
from qcom.scenarios import tier2_config, run_twin


@dataclass
class SobolProblem:
    names: list[str]
    bounds: list[tuple[float, float]]

    @property
    def dim(self) -> int:
        return len(self.names)


def default_problem() -> SobolProblem:
    return SobolProblem(
        names=["orders_per_day", "batch_target", "aov", "ad_take"],
        bounds=[(300.0, 900.0), (1.0, 3.0), (520.0, 720.0), (0.0, 0.05)],
    )


def _scale(unit: np.ndarray, bounds: list[tuple[float, float]]) -> np.ndarray:
    out = np.empty_like(unit)
    for j, (lo, hi) in enumerate(bounds):
        out[:, j] = lo + unit[:, j] * (hi - lo)
    return out


def saltelli_matrices(problem: SobolProblem, n: int, seed: int = 0) -> np.ndarray:
    """Build the Saltelli sample stack: A, B, then D matrices A_B^i.

    Returns an array of shape (n * (D + 2), D) in evaluation order:
    rows [0:n] = A, [n:2n] = B, [2n:3n] = A with col 0 from B, etc.
    """
    rng = np.random.default_rng(seed)
    d = problem.dim
    base = rng.random((n, 2 * d))
    A = _scale(base[:, :d], problem.bounds)
    B = _scale(base[:, d:], problem.bounds)
    blocks = [A, B]
    for i in range(d):
        ABi = A.copy()
        ABi[:, i] = B[:, i]
        blocks.append(ABi)
    return np.vstack(blocks)


def evaluate_model(cost: CostModel, problem: SobolProblem, X: np.ndarray,
                   replications: int = 3, seed: int = 5) -> np.ndarray:
    """Run the twin for every sampled lever vector; return contribution margins."""
    y = np.empty(X.shape[0])
    for k in range(X.shape[0]):
        opd, batch, aov, ad = X[k]
        cfg = tier2_config(orders_per_day=float(opd), batch_target=int(round(batch)))
        t = run_twin(cfg, cost, aov=float(aov), ad_take=float(ad),
                     replications=replications, seed=seed)
        y[k] = t.contribution
    return y


@dataclass
class SobolResult:
    names: list[str]
    S1: np.ndarray
    ST: np.ndarray

    def ranked(self) -> list[tuple[str, float, float]]:
        order = np.argsort(-self.ST)
        return [(self.names[i], float(self.S1[i]), float(self.ST[i])) for i in order]

    def as_dict(self) -> dict:
        return {
            "names": self.names,
            "S1": [float(x) for x in self.S1],
            "ST": [float(x) for x in self.ST],
        }


def sobol_indices(problem: SobolProblem, y: np.ndarray, n: int) -> SobolResult:
    """Jansen first-order and total Sobol estimators from a Saltelli output vector."""
    d = problem.dim
    yA = y[:n]
    yB = y[n : 2 * n]
    var = np.var(np.concatenate([yA, yB]), ddof=1)
    S1 = np.empty(d)
    ST = np.empty(d)
    for i in range(d):
        yABi = y[(2 + i) * n : (3 + i) * n]
        # Jansen 1999 estimators.
        S1[i] = (var - 0.5 * np.mean((yB - yABi) ** 2)) / var if var > 0 else 0.0
        ST[i] = (0.5 * np.mean((yA - yABi) ** 2)) / var if var > 0 else 0.0
    return SobolResult(names=problem.names, S1=S1, ST=ST)


def run_sobol(cost: CostModel, n: int = 64, replications: int = 3,
              seed: int = 0) -> SobolResult:
    problem = default_problem()
    X = saltelli_matrices(problem, n, seed=seed)
    y = evaluate_model(cost, problem, X, replications=replications, seed=seed + 5)
    return sobol_indices(problem, y, n)
