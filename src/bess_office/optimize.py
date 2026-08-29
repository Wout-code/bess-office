"""LP-based battery dispatch optimization, using Pyomo.

Same physical battery model and input format as dispatch_sim.py (V1),
but decides charge/discharge by solving a single linear program over
the full horizon at once, instead of applying reactive priority rules.
See ASSUMPTIONS.md (V2) for what changes vs. the rule-based baseline:
grid-charging allowed, peak threshold optimized internally (not a fixed
input), costs inside the objective, perfect-forecast horizon (a known
simplification -- see ROADMAP.md Fase 3 for the MPC follow-up that
removes it).

Cost has two components (energy + peak), both already in EUR -- this is
a single-objective LP with a richer cost function, not multi-objective
optimization (see ROADMAP.md Fase 2 for why that distinction matters).

Requires a solver Pyomo can call, e.g. CBC (`conda install -c
conda-forge coincbc`, or download a CBC binary) or HiGHS (`pip install
highspy`, then SolverFactory("appsi_highs")). This file defaults to CBC.
"""

import pandas as pd
import pyomo.environ as pyo

from bess_office.config import BatteryConfig, GridTariffConfig


def run_lp_dispatch(
    pv_kwh: pd.Series,
    load_kwh: pd.Series,
    prices_eur_mwh: pd.Series, #waar komt dit vandaan
    battery: BatteryConfig,
    grid_tariff: GridTariffConfig,   # deze klopt niet is nog niet ingevuld in config.py
    timestep_hours: float,   
) -> pd.DataFrame:
    """
    Solve a single linear program for battery dispatch over the full
    horizon, minimizing total cost (energy + peak/capacity).

    Parameters
    ----------
    pv_kwh, load_kwh : pd.Series
        Same units/index requirements as dispatch_sim.py's
        run_baseline_dispatch -- energy in kWh per timestep.
    prices_eur_mwh : pd.Series
        Day-ahead prices, same index as pv_kwh/load_kwh.
    battery : BatteryConfig
        Same battery model as V1. Note: asymmetric charge/discharge
        power (see ASSUMPTIONS.md) is not yet split into separate
        limits here -- power_kw is still used for both directions.
    grid_tariff : GridTariffConfig
        contracted_capacity_tariff_eur_per_kw must be set (not None --
        see the TODO in config.py). This is EUR per kW of peak import;
        the LP minimizes this jointly with energy cost, so the
        "threshold" is a model output, not an input, unlike V1.
    timestep_hours : float
        Length of each timestep, e.g. 0.25 for quarter-hour data.

    Returns
    -------
    pd.DataFrame
        Same columns as run_baseline_dispatch's output, for direct
        comparison in main.py.
    """
    if not (pv_kwh.index.equals(load_kwh.index) and pv_kwh.index.equals(prices_eur_mwh.index)):
        raise ValueError(
            "pv_kwh, load_kwh and prices_eur_mwh must share the same index."
        )
    if grid_tariff.contracted_capacity_tariff_eur_per_kw is None:
        raise ValueError(
            "grid_tariff.contracted_capacity_tariff_eur_per_kw is still None "
            "-- fill in a real tariff (see config.py TODO) before running the LP."
        )

    timestamps = list(pv_kwh.index)
    prices_eur_kwh = (prices_eur_mwh / 1000).to_numpy()
    pv = pv_kwh.to_numpy()
    load = load_kwh.to_numpy()

    min_soc = battery.min_soc_fraction * battery.capacity_kwh
    max_soc = battery.max_soc_fraction * battery.capacity_kwh
    initial_soc = battery.initial_soc_fraction * battery.capacity_kwh
    max_energy_per_step = battery.power_kw * timestep_hours

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(0, len(timestamps) - 1)

    # Decision variables
    model.charge = pyo.Var(model.T, bounds=(0, max_energy_per_step))
    model.discharge = pyo.Var(model.T, bounds=(0, max_energy_per_step))
    model.soc = pyo.Var(model.T, bounds=(min_soc, max_soc))
    model.grid_import = pyo.Var(model.T, bounds=(0, None))
    model.grid_export = pyo.Var(model.T, bounds=(0, None))
    # "Geoptimaliseerde peak-drempel" (ASSUMPTIONS.md) -- geen vaste
    # input, de solver kiest zelf de kostenminimaliserende piek.
    model.peak_import_kw = pyo.Var(bounds=(0, None))

    # LET OP (BAT-7 in ASSUMPTIONS.md): geen binaire constraint die
    # simultaan laden/ontladen verbiedt. De aanname is dat de solver dit
    # vanzelf vermijdt omdat het via round_trip_efficiency < 1 altijd
    # verlies oplevert -- behalve mogelijk bij negatieve prijzen.
    # Check na het oplossen: (result["charge_kwh"] > 0) & (result["discharge_kwh"] > 0)
    # zou overal False moeten zijn. Zo niet: dit wordt een MILP met een
    # binaire is_charging-variabele per tijdstap.

    def soc_rule(m, t):
        prev_soc = initial_soc if t == 0 else m.soc[t - 1]
        # Zelfde vereenvoudiging als V1: ontladen is verliesvrij,
        # laadverlies zit alleen bij het laden (ASSUMPTIONS.md, Batterij).
        return m.soc[t] == prev_soc + m.charge[t] * battery.round_trip_efficiency - m.discharge[t]

    model.soc_dynamics = pyo.Constraint(model.T, rule=soc_rule)

    def balance_rule(m, t):
        # (load + charge) gedekt door (pv + discharge + import), rest export.
        return load[t] + m.charge[t] == pv[t] + m.discharge[t] + m.grid_import[t] - m.grid_export[t]

    model.energy_balance = pyo.Constraint(model.T, rule=balance_rule)

    def peak_rule(m, t):
        # peak_import_kw moet minstens elke import zijn -- de solver
        # drukt 'm zo laag mogelijk, want hij kost geld in de objective.
        return m.peak_import_kw >= m.grid_import[t] / timestep_hours

    model.peak_constraint = pyo.Constraint(model.T, rule=peak_rule)

    def objective_rule(m):
        energy_cost = sum(
            (m.grid_import[t] - m.grid_export[t]) * prices_eur_kwh[t] for t in m.T
        )
        peak_cost = m.peak_import_kw * grid_tariff.contracted_capacity_tariff_eur_per_kw
        return energy_cost + peak_cost

    model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    solver = pyo.SolverFactory("cbc")
    solver_result = solver.solve(model, tee=False)

    if solver_result.solver.termination_condition != pyo.TerminationCondition.optimal:
        raise RuntimeError(
            f"LP niet optimaal opgelost: {solver_result.solver.termination_condition}"
        )

    records = []
    for t, timestamp in enumerate(timestamps):
        records.append(
            {
                "timestamp": timestamp,
                "pv_kwh": pv[t],
                "load_kwh": load[t],
                "soc_kwh": pyo.value(model.soc[t]),
                "charge_kwh": pyo.value(model.charge[t]),
                "discharge_kwh": pyo.value(model.discharge[t]),
                "grid_import_kwh": pyo.value(model.grid_import[t]),
                "grid_export_kwh": pyo.value(model.grid_export[t]),
            }
        )

    return pd.DataFrame(records).set_index("timestamp")


if __name__ == "__main__":
    # Kleine, synthetische test -- zelfde aanpak als dispatch_sim.py's
    # eigen __main__-blok: losse logica-check met kleine, verifieerbare
    # data, geen echte databronnen (die integratie hoort in main.py).
    import numpy as np

    hours = pd.date_range("2023-06-01", periods=24, freq="1h")
    pv = pd.Series(
        np.clip(5 * np.sin((hours.hour - 6) / 12 * np.pi), 0, None), index=hours
    )
    load = pd.Series(
        [2, 2, 2, 2, 2, 3, 5, 6, 4, 3, 3, 3, 3, 3, 3, 4, 6, 7, 6, 4, 3, 2, 2, 2],
        index=hours,
    )
    prices = pd.Series(
        [50, 48, 45, 44, 45, 50, 70, 90, 80, 60, 55, 50,
         48, 50, 55, 65, 100, 120, 95, 70, 60, 55, 52, 50],
        index=hours,
    )

    battery = BatteryConfig(capacity_kwh=10, power_kw=5)
    grid_tariff = GridTariffConfig(contracted_capacity_tariff_eur_per_kw=5.0)

    result = run_lp_dispatch(pv, load, prices, battery, grid_tariff, timestep_hours=1.0)
    print(result)

    energy_cost = (result["grid_import_kwh"] - result["grid_export_kwh"]) * prices.values / 1000
    peak_kw = (result["grid_import_kwh"] / 1.0).max()
    print(f"\nPiek-import: {peak_kw:.2f} kW")
    print(f"Energiekosten: €{energy_cost.sum():.2f}")
    print(f"Piekkosten:    €{peak_kw * grid_tariff.contracted_capacity_tariff_eur_per_kw:.2f}")