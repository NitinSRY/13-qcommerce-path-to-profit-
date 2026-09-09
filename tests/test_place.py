from qcom.geo import GridCity
from qcom.place import FacilityLocator


def _locator():
    city = GridCity.synthetic(n=10, cell_km=1.0, seed=2)
    return FacilityLocator(city, service_km=2.0, candidate_stride=2)


def test_greedy_picks_requested_count():
    loc = _locator()
    chosen = loc.greedy(3)
    assert len(chosen) == 3
    assert len(set(chosen)) == 3  # distinct sites


def test_local_search_not_worse_than_greedy():
    loc = _locator()
    g = loc.greedy(3)
    ls = loc.local_search(g)
    assert loc._covered_demand(ls) >= loc._covered_demand(g) - 1e-6


def test_optimized_beats_or_matches_naive():
    loc = _locator()
    opt = loc.solve(4, with_bound=False)
    naive = loc.equal_spacing(4)
    assert opt.covered_demand >= naive.covered_demand - 1e-6


def test_coverage_within_lp_bound():
    loc = _locator()
    res = loc.solve(3, with_bound=True)
    # The heuristic can never exceed the LP relaxation upper bound.
    assert res.covered_demand <= res.lp_upper_bound + 1e-6
    assert 0.0 <= res.optimality_gap <= 1.0


def test_more_stores_cover_more():
    loc = _locator()
    a = loc.solve(2, with_bound=False)
    b = loc.solve(5, with_bound=False)
    assert b.covered_demand >= a.covered_demand
