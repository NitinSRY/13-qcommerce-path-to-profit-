import numpy as np

from qcom.geo import GridCity
from qcom.demand import DemandModel


def test_capture_probabilities_bounded():
    city = GridCity.synthetic(n=10, cell_km=1.0)
    dm = DemandModel(city, max_serve_km=3.0)
    probs = dm.capture_probabilities([(2, 2), (7, 7)])
    # Each cell's capture across stores is a probability (<= 1, never negative).
    assert probs.shape == (100, 2)
    assert (probs >= 0).all()
    assert (probs.sum(axis=1) <= 1.0 + 1e-9).all()


def test_more_stores_capture_more_demand():
    city = GridCity.synthetic(n=12, cell_km=0.8)
    dm = DemandModel(city)
    one = dm.covered_demand_fraction([(6, 6)])
    two = dm.covered_demand_fraction([(3, 3), (9, 9)])
    assert two > one


def test_closer_store_captures_more():
    city = GridCity.synthetic(n=12, cell_km=0.8, seed=1)
    dm = DemandModel(city, beta=2.0)
    # A store on the dense centre should out-capture a store in a corner.
    center = (6, 6)
    corner = (0, 0)
    rates = dm.store_order_rates([center, corner])
    assert rates[0] > rates[1]


def test_order_rates_nonnegative():
    city = GridCity.synthetic(n=8, cell_km=1.0)
    dm = DemandModel(city)
    rates = dm.store_order_rates([(4, 4)])
    assert (rates >= 0).all()
