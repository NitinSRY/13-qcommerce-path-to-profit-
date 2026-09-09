import numpy as np

from qcom.sensitivity import (
    SobolProblem,
    saltelli_matrices,
    sobol_indices,
    default_problem,
)


def test_saltelli_matrix_shape():
    prob = default_problem()
    n = 8
    X = saltelli_matrices(prob, n, seed=0)
    assert X.shape == (n * (prob.dim + 2), prob.dim)
    # Samples lie within the declared bounds.
    for j, (lo, hi) in enumerate(prob.bounds):
        assert X[:, j].min() >= lo - 1e-9
        assert X[:, j].max() <= hi + 1e-9


def test_sobol_recovers_known_attribution():
    # Analytic test on the Ishigami-like additive model where x0 dominates:
    # y = 3*x0 + 1*x1 + 0*x2 over [0,1]^3. First-order variance share of x0 >> x1 >> x2.
    prob = SobolProblem(names=["x0", "x1", "x2"], bounds=[(0, 1), (0, 1), (0, 1)])
    n = 4096
    X = saltelli_matrices(prob, n, seed=1)
    y = 3 * X[:, 0] + 1 * X[:, 1] + 0 * X[:, 2]
    res = sobol_indices(prob, y, n)
    assert res.S1[0] > res.S1[1] > res.S1[2]
    # Additive model: total ~ first order; x0 carries ~9/10 of the variance.
    assert 0.85 < res.S1[0] < 0.95
    assert res.S1[2] < 0.05


def test_sobol_indices_in_unit_range():
    prob = SobolProblem(names=["a", "b"], bounds=[(0, 1), (0, 1)])
    n = 1024
    X = saltelli_matrices(prob, n, seed=2)
    y = X[:, 0] ** 2 + X[:, 1]
    res = sobol_indices(prob, y, n)
    assert (res.ST >= -0.05).all()
    assert (res.S1 <= 1.05).all()
