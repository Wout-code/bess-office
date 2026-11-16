"""Tests for the rule-based dispatch (dispatch_sim.py).

Draaien bewust met timestep_hours=0.25: bij uurdata is kWh == kW en
blijven eenheidsfouten onzichtbaar (zie CLAUDE.md, Eenheden).
"""

import pandas as pd
import pytest

from bess_office.config import BatteryConfig
from bess_office.dispatch_sim import compute_dispatch_metrics, run_baseline_dispatch

DT = 0.25  # uur per tijdstap (kwartier)
THRESHOLD_KW = 40.0


def _series(values_kw: list[float]) -> pd.Series:
    """Build a quarter-hour kWh series from a list of power values in kW."""
    index = pd.date_range("2023-01-02 08:00", periods=len(values_kw), freq="15min", tz="Europe/Amsterdam")
    return pd.Series([v * DT for v in values_kw], index=index, dtype=float)


@pytest.fixture
def battery() -> BatteryConfig:
    return BatteryConfig(capacity_kwh=100.0, power_kw=50.0)


def test_rbc_discharges_above_threshold_and_not_below(battery):
    load_kw = [60.0, 60.0, 20.0, 20.0, 60.0]
    load = _series(load_kw)
    pv = _series([0.0] * len(load_kw))

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    above = [lk > THRESHOLD_KW for lk in load_kw]
    assert (result.loc[above, "discharge_kwh"] > 0).all()
    # Import teruggebracht tot precies de drempel (genoeg SoC beschikbaar).
    assert result.loc[above, "grid_import_kwh"].div(DT).to_numpy() == pytest.approx(THRESHOLD_KW)
    below = [not a for a in above]
    assert (result.loc[below, "discharge_kwh"] == 0).all()


def test_metrics_report_peaks_in_kw(battery):
    load = _series([60.0, 20.0, 20.0])
    pv = _series([0.0, 0.0, 0.0])

    result = run_baseline_dispatch(pv, load, battery, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)
    metrics = compute_dispatch_metrics(result, peak_threshold_kw=THRESHOLD_KW, timestep_hours=DT)

    assert metrics["peak_import_no_battery_kw"] == pytest.approx(60.0)  # niet 15 (kWh/kwartier)
    assert metrics["peak_import_with_battery_kw"] == pytest.approx(THRESHOLD_KW)
