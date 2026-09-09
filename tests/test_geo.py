import numpy as np

from qcom.geo import GridCity, haversine_km


def test_haversine_zero():
    assert haversine_km(26.85, 80.95, 26.85, 80.95) == 0.0


def test_haversine_known_distance():
    # ~1 degree of latitude is ~111 km.
    d = haversine_km(0.0, 0.0, 1.0, 0.0)
    assert 110.0 < d < 112.0


def test_grid_shapes_and_population():
    city = GridCity.synthetic(n=10, cell_km=1.0)
    assert city.n_cells == 100
    assert city.cell_population().shape == (10, 10)
    assert city.total_population() > 0
    assert city.centroids().shape == (100, 2)


def test_road_distance_uses_detour():
    city = GridCity.synthetic(n=8, cell_km=1.0, detour=2.0)
    straight = haversine_km(*city.latlon(0, 0), *city.latlon(0, 3))
    road = city.road_km((0, 0), (0, 3))
    assert np.isclose(road, straight * 2.0)


def test_density_validation():
    import pytest

    with pytest.raises(ValueError):
        GridCity(n=4, cell_km=1.0, center=(0, 0), density=np.zeros((3, 3)))
