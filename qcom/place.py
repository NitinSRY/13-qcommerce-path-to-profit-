"""From-scratch facility-location optimizer for dark-store placement.

Where do you put N dark stores on the demand grid to capture the most
*profitable* demand? This is a p-median / maximal-covering style problem: choose
N of the candidate cells to maximise covered demand within the service radius. It
is NP-hard, so we solve it with a greedy seed plus local search (swap moves) and
bound the optimality gap with an LP relaxation solved by scipy's linprog.

"Profitable" demand matters: a store only helps if the demand it captures clears
the breakeven order density. We therefore weight coverage by demand and report
the gap to the LP upper bound so the heuristic's quality is auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from qcom.geo import GridCity


@dataclass
class PlacementResult:
    store_cells: list[tuple[int, int]]
    covered_demand: float
    total_demand: float
    lp_upper_bound: float

    @property
    def covered_fraction(self) -> float:
        return self.covered_demand / self.total_demand if self.total_demand else 0.0

    @property
    def optimality_gap(self) -> float:
        """Relative gap of the heuristic to the LP upper bound (smaller = better)."""
        if self.lp_upper_bound <= 0:
            return 0.0
        return max(0.0, (self.lp_upper_bound - self.covered_demand) / self.lp_upper_bound)


class FacilityLocator:
    def __init__(self, city: GridCity, service_km: float = 2.0, candidate_stride: int = 1):
        self.city = city
        self.service_km = service_km
        # Candidate sites: a subsample of cells for tractability on big grids.
        self.candidates = [
            (i, j)
            for i in range(0, city.n, candidate_stride)
            for j in range(0, city.n, candidate_stride)
        ]
        self.demand = city.cell_population().reshape(-1)
        self._build_coverage()

    def _build_coverage(self) -> None:
        """Boolean coverage matrix: candidate s covers demand cell c if within radius."""
        n_cells = self.city.n_cells
        cand = self.candidates
        cover = np.zeros((len(cand), n_cells), dtype=bool)
        for s, sc in enumerate(cand):
            for c in range(n_cells):
                ij = divmod(c, self.city.n)
                if self.city.road_km(sc, ij) <= self.service_km:
                    cover[s, c] = True
        self.cover = cover

    def _covered_demand(self, chosen: list[int]) -> float:
        if not chosen:
            return 0.0
        covered = np.any(self.cover[chosen], axis=0)
        return float(self.demand[covered].sum())

    def greedy(self, n_stores: int) -> list[int]:
        """Greedy maximal coverage: repeatedly add the site with the best marginal gain."""
        chosen: list[int] = []
        covered = np.zeros(self.city.n_cells, dtype=bool)
        for _ in range(n_stores):
            best_gain, best_s = -1.0, None
            for s in range(len(self.candidates)):
                if s in chosen:
                    continue
                gain = self.demand[self.cover[s] & ~covered].sum()
                if gain > best_gain:
                    best_gain, best_s = gain, s
            if best_s is None:
                break
            chosen.append(best_s)
            covered |= self.cover[best_s]
        return chosen

    def local_search(self, chosen: list[int], max_iter: int = 100) -> list[int]:
        """Improve the greedy solution with 1-swap moves until no swap helps."""
        chosen = list(chosen)
        best = self._covered_demand(chosen)
        for _ in range(max_iter):
            improved = False
            for idx in range(len(chosen)):
                for s in range(len(self.candidates)):
                    if s in chosen:
                        continue
                    trial = chosen.copy()
                    trial[idx] = s
                    val = self._covered_demand(trial)
                    if val > best + 1e-9:
                        chosen, best, improved = trial, val, True
                        break
                if improved:
                    break
            if not improved:
                break
        return chosen

    def lp_upper_bound(self, n_stores: int) -> float:
        """LP relaxation of maximal covering, giving an upper bound on coverage.

        Variables: y_s in [0,1] (open site s), z_c in [0,1] (cell c covered).
        Maximise sum_c demand_c * z_c  s.t.  z_c <= sum_{s covers c} y_s,
        sum_s y_s <= n_stores. linprog minimises, so we negate the objective.
        """
        n_s = len(self.candidates)
        n_c = self.city.n_cells
        n_var = n_s + n_c  # [y ; z]

        c_obj = np.zeros(n_var)
        c_obj[n_s:] = -self.demand  # maximise demand*z -> minimise -demand*z

        rows, data, cols, b = [], [], [], []
        row = 0
        # z_c - sum_{s covers c} y_s <= 0
        A_ub_rows = []
        b_ub = []
        for c in range(n_c):
            coeff = np.zeros(n_var)
            coeff[n_s + c] = 1.0
            covering = np.where(self.cover[:, c])[0]
            coeff[covering] = -1.0
            A_ub_rows.append(coeff)
            b_ub.append(0.0)
        # sum_s y_s <= n_stores
        coeff = np.zeros(n_var)
        coeff[:n_s] = 1.0
        A_ub_rows.append(coeff)
        b_ub.append(float(n_stores))

        res = linprog(
            c_obj,
            A_ub=np.array(A_ub_rows),
            b_ub=np.array(b_ub),
            bounds=[(0, 1)] * n_var,
            method="highs",
        )
        if not res.success:
            return float("inf")
        return float(-res.fun)

    def solve(self, n_stores: int, with_bound: bool = True) -> PlacementResult:
        chosen = self.local_search(self.greedy(n_stores))
        bound = self.lp_upper_bound(n_stores) if with_bound else float("inf")
        return PlacementResult(
            store_cells=[self.candidates[s] for s in chosen],
            covered_demand=self._covered_demand(chosen),
            total_demand=float(self.demand.sum()),
            lp_upper_bound=bound,
        )

    def _nearest_candidate(self, cell: tuple[int, int]) -> int:
        """Index of the candidate site closest to an arbitrary cell."""
        ci, cj = cell
        best, best_d = 0, float("inf")
        for s, (si, sj) in enumerate(self.candidates):
            d = (si - ci) ** 2 + (sj - cj) ** 2
            if d < best_d:
                best, best_d = s, d
        return best

    def equal_spacing(self, n_stores: int) -> PlacementResult:
        """Naive baseline: place stores on a coarse regular lattice.

        Each lattice point is snapped to the nearest candidate site so the
        baseline is always realisable on the same candidate grid as the optimizer.
        """
        import math

        side = max(1, int(math.ceil(math.sqrt(n_stores))))
        step = self.city.n / (side + 1)
        chosen: list[int] = []
        for a in range(1, side + 1):
            for b in range(1, side + 1):
                if len(chosen) >= n_stores:
                    break
                s = self._nearest_candidate((int(a * step), int(b * step)))
                if s not in chosen:
                    chosen.append(s)
        return PlacementResult(
            store_cells=[self.candidates[s] for s in chosen],
            covered_demand=self._covered_demand(chosen),
            total_demand=float(self.demand.sum()),
            lp_upper_bound=float("inf"),
        )
