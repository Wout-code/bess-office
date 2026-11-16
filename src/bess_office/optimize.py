"""LP-based battery dispatch optimization, using Pyomo.

Same physical battery model and input format as dispatch_sim.py (V1),
but decides charge/discharge by solving a single linear program over
the full horizon at once, instead of applying reactive priority rules.
See ASSUMPTIONS.md (V2) for what changes vs. the rule-based baseline:
grid-charging allowed, peak threshold optimized internally (not a fixed
input), costs inside the objective, perfect-forecast horizon (a known
simplification -- see ROADMAP.md Fase 3 for the MPC follow-up that
removes it).

Cost has two components (energy + monthly peak), both already in EUR --
this is a single-objective LP with a richer cost function, not
multi-objective optimization (see ROADMAP.md Fase 2 for why that
distinction matters).

Requires a solver Pyomo can call, e.g. CBC (`conda install -c
conda-forge coincbc`, or download a CBC binary) or HiGHS (`pip install
highspy`, then SolverFactory("appsi_highs")). This file defaults to CBC.
"""

# Open, nog niet opgelost in dit bestand (zie ASSUMPTIONS.md / z.TODO.md):
# - BAT-7: asymmetrisch laad-/ontlaadvermogen nog niet verwerkt, power_kw
#   wordt nog voor beide richtingen gebruikt.
# - BAT-3: geen degradatiekost -- de solver ziet cyclen als gratis. Dit is
#   ook de reden voor de negatieve-prijzen-loophole: zonder een kost op
#   doorstroom kan gelijktijdig laden/ontladen bij prijs < 0 fysisch
#   onzinnig maar LP-optimaal lijken.
# - BAT-4: geen minimale aan/uit-tijd, batterij kan elk kwartier wisselen.
# - GTV/jaarlijkse-overschrijding-component (zie config.py GridTariffConfig)
#   wordt NIET gemodelleerd -- bewuste vereenvoudiging, zie daar voor
#   details en de TODO om dit later toe te voegen.
#
# Dit gesprek gefixt, samengevat (zie het statusoverzicht-document voor de
# volledige geschiedenis van deze paar stappen):
# - transport_tariff_eur_per_kwh ontbrak volledig uit energy_cost -- nu
#   toegevoegd, alleen op import (export betaalt geen transporttarief,
#   zie ASSUMPTIONS.md ARCH-5).
# - Piekkost gebruikte eerst het verkeerde tariefveld, en later een
#   aanname over een jaarlijks GTV/overschrijdingsmechanisme die bij
#   verificatie tegen Liander's eigen tarievendocument onvolledig bleek:
#   er bestaat namelijk een APARTE, maandelijkse piekcomponent ("kW max.
#   mnd" in Liander's tabel) naast de jaarlijkse GTV-component. Dit
#   bestand modelleert nu alleen die maandelijkse component (bewuste
#   vereenvoudiging, zie config.py) -- peak_import_kw is dus weer per
#   kalendermaand, net als de eerdere versie, maar nu met een eerlijk
#   benoemd tariefveld (monthly_peak_tariff_eur_per_kw) in plaats van een
#   verkeerd begrepen "overshoot penalty" of "GTV-tarief."

import pandas as pd
import pyomo.environ as pyo

from bess_office.config import BatteryConfig, GridTariffConfig


def run_lp_dispatch(
    pv_kwh: pd.Series,
    load_kwh: pd.Series,
    prices_eur_mwh: pd.Series,
    battery: BatteryConfig,
    grid_tariff: GridTariffConfig,
    timestep_hours: float,
) -> pd.DataFrame:
    """
    Solve a single linear program for battery dispatch over the full
    horizon, minimizing total cost (energy + transport + monthly peak).

    Parameters
    ----------
    pv_kwh, load_kwh : pd.Series
        Same units/index requirements as dispatch_sim.py's
        run_baseline_dispatch -- energy in kWh per timestep. These are
        FIXED inputs, not decision variables: the LP never reshapes
        load or PV, it only decides charge/discharge/import/export
        around them.
    prices_eur_mwh : pd.Series
        Day-ahead prices, same index as pv_kwh/load_kwh.
    battery : BatteryConfig
        Same battery model as V1. Note: asymmetric charge/discharge
        power (BAT-7, see ASSUMPTIONS.md) is not yet split into separate
        limits here -- power_kw is still used for both directions.
    grid_tariff : GridTariffConfig
        Components used here (see config.py docstring for the full
        picture and what is deliberately left out):
        - transport_tariff_eur_per_kwh: EUR per kWh of grid import.
        - energy_tax_eur_per_kwh: EUR per kWh of grid import (NET-5).
        - storage_charge_tax_eur_per_kwh: EUR per kWh charged into the
          battery; 0.0 except in the storage double-tax scenario (NET-6).
        - monthly_peak_tariff_eur_per_kw: EUR per kW of the highest
          import in a calendar month, charged separately per month
          (Liander's "kW max. mnd" component). The GTV/annual-contract
          component is NOT modeled here.
        Both must be set (not None).
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
    if grid_tariff.transport_tariff_eur_per_kwh is None:
        raise ValueError(
            "grid_tariff.transport_tariff_eur_per_kwh is still None "
            "-- fill in a real tariff (see config.py TODO) before running the LP."
        )
    if grid_tariff.monthly_peak_tariff_eur_per_kw is None:
        raise ValueError(
            "grid_tariff.monthly_peak_tariff_eur_per_kw is still None "
            "-- fill in a real tariff (see config.py TODO) before running the LP."
        )

    timestamps = list(pv_kwh.index)
    prices_eur_kwh = (prices_eur_mwh / 1000).to_numpy()  # EUR/MWh -> EUR/kWh
    pv = pv_kwh.to_numpy()
    load = load_kwh.to_numpy()

    # Kalendermaand per tijdstap, voor de maandpiek-constraint. timestamps
    # zijn al tz-aware Europe/Amsterdam (zie ASSUMPTIONS.md DATA-1), dus dit
    # volgt lokale kloktijd, niet UTC -- consistent met hoe het tarief in
    # werkelijkheid wordt afgerekend.
    months = pd.Series(timestamps).dt.to_period("M").astype(str)
    unique_months = sorted(months.unique())

    min_soc = battery.min_soc_fraction * battery.capacity_kwh
    max_soc = battery.max_soc_fraction * battery.capacity_kwh
    initial_soc = battery.initial_soc_fraction * battery.capacity_kwh
    max_energy_per_step = battery.power_kw * timestep_hours

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(0, len(timestamps) - 1)
    model.M = pyo.Set(initialize=unique_months)

    # Decision variables
    model.charge = pyo.Var(model.T, bounds=(0, max_energy_per_step))
    model.discharge = pyo.Var(model.T, bounds=(0, max_energy_per_step))
    model.soc = pyo.Var(model.T, bounds=(min_soc, max_soc))
    model.grid_import = pyo.Var(model.T, bounds=(0, None))
    model.grid_export = pyo.Var(model.T, bounds=(0, None))
    # Eén piek-variabele per kalendermaand -- modelleert Liander's "kW max.
    # mnd"-component (zie config.py). Geen floor tegen een gecontracteerd
    # vermogen: die GTV-component is in dit vereenvoudigde model niet
    # meegenomen.
    model.peak_import_kw = pyo.Var(model.M, bounds=(0, None))

    def soc_rule(m, t):
        prev_soc = initial_soc if t == 0 else m.soc[t - 1]
        # laadverlies zit alleen bij het laden (ASSUMPTIONS.md BAT-2)
        return m.soc[t] == prev_soc + m.charge[t] * battery.round_trip_efficiency - m.discharge[t]

    model.soc_dynamics = pyo.Constraint(model.T, rule=soc_rule)

    # Eind-SoC minstens begin-SoC (BAT-9): anders trekt de LP de batterij aan
    # het eind van de horizon gratis leeg en telt die energie als winst.
    model.terminal_soc = pyo.Constraint(expr=model.soc[len(timestamps) - 1] >= initial_soc)

    def balance_rule(m, t):
        # (load + charge) gedekt door (pv + discharge + import), rest export.
        return load[t] + m.charge[t] == pv[t] + m.discharge[t] + m.grid_import[t] - m.grid_export[t]

    model.energy_balance = pyo.Constraint(model.T, rule=balance_rule)

    def peak_rule(m, t):
        # peak_import_kw van de maand waar tijdstap t in valt moet minstens
        # deze import zijn -- de solver drukt 'm zo laag mogelijk per maand,
        # want elke maand kost apart geld in de objective.
        month = months.iloc[t]
        return m.peak_import_kw[month] >= m.grid_import[t] / timestep_hours

    model.peak_constraint = pyo.Constraint(model.T, rule=peak_rule)

    def objective_rule(m):
        energy_cost = sum(
            (m.grid_import[t] - m.grid_export[t]) * prices_eur_kwh[t]
            + m.grid_import[t] * grid_tariff.transport_tariff_eur_per_kwh
            # energiebelasting alleen op import, geen saldering (NET-5)
            + m.grid_import[t] * grid_tariff.energy_tax_eur_per_kwh
            # scenario B: belasting op alles wat de batterij in gaat (NET-6)
            + m.charge[t] * grid_tariff.storage_charge_tax_eur_per_kwh
            for t in m.T
        )
        peak_cost = sum(m.peak_import_kw[month] for month in m.M) * grid_tariff.monthly_peak_tariff_eur_per_kw
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
    # Kleine, synthetische test -- eigen __main__-blok: losse logica-check
    # met kleine, verifieerbare data, geen echte databronnen. Dekt meerdere
    # maanden, anders test je de maandpiek-logica niet zinnig.
    import numpy as np

    hours = pd.date_range("2023-06-25", periods=24 * 10, freq="1h", tz="Europe/Amsterdam")
    hour_of_day = hours.hour.to_numpy()
    day_pattern = np.clip(5 * np.sin((hour_of_day - 6) / 12 * np.pi), 0, None)
    pv = pd.Series(day_pattern, index=hours)

    load_pattern = np.array(
        [2, 2, 2, 2, 2, 3, 5, 6, 4, 3, 3, 3, 3, 3, 3, 4, 6, 7, 6, 4, 3, 2, 2, 2]
    )
    load = pd.Series(np.tile(load_pattern, 10), index=hours)

    rng = np.random.default_rng(seed=0)
    price_pattern = np.array(
        [50, 48, 45, 44, 45, 50, 70, 90, 80, 60, 55, 50,
         48, 50, 55, 65, 100, 120, 95, 70, 60, 55, 52, 50]
    )
    prices = pd.Series(
        np.tile(price_pattern, 10) + rng.normal(0, 3, 24 * 10), index=hours
    )

    battery = BatteryConfig(capacity_kwh=10, power_kw=5)
    grid_tariff = GridTariffConfig(
        transport_tariff_eur_per_kwh=0.02,       # placeholder, NIET een echt Liander-tarief
        monthly_peak_tariff_eur_per_kw=5.0,      # placeholder, NIET een echt Liander-tarief
    )

    result = run_lp_dispatch(pv, load, prices, battery, grid_tariff, timestep_hours=1.0)
    print(result)

    energy_cost = (
        (result["grid_import_kwh"] - result["grid_export_kwh"]) * prices.values / 1000
        + result["grid_import_kwh"] * grid_tariff.transport_tariff_eur_per_kwh
    )
    monthly_peak = (result["grid_import_kwh"] / 1.0).groupby(result.index.to_period("M")).max()
    peak_cost = monthly_peak.sum() * grid_tariff.monthly_peak_tariff_eur_per_kw

    print(f"\nPiek-import per maand (kW):\n{monthly_peak}")
    print(f"\nEnergie- + transportkosten: €{energy_cost.sum():.2f}")
    print(f"Piekkosten (alle maanden):  €{peak_cost:.2f}")