import numpy as np
from scipy.stats import gaussian_kde

from domains.reporting.services.simulation_data_service import SimulationDataService


def test_build_distribution_uses_scenario_analysis_kde_shape() -> None:
    values = [1.0, 2.0, 3.0, 5.0, 8.0]

    result = SimulationDataService().build_distribution(values, bins=60)

    x_grid = np.linspace(min(values), max(values), 500)
    expected_density = gaussian_kde(np.array(values, dtype="float64"), bw_method="scott")(x_grid)
    expected_density[0] = 0.0
    expected_density[-1] = 0.0

    assert result.x_grid == x_grid.tolist()
    assert result.density == expected_density.tolist()
    assert result.median == 3.0
    assert result.values == values


def test_build_distribution_constant_values_matches_scenario_analysis_empty_density() -> None:
    result = SimulationDataService().build_distribution([7.0, 7.0, 7.0], bins=60)

    assert len(result.x_grid) == 500
    assert result.x_grid[0] == 6.0
    assert result.x_grid[-1] == 8.0
    assert result.density == [0.0] * 500
    assert result.median == 7.0
    assert result.values == [7.0, 7.0, 7.0]
