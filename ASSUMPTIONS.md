# Assumptions — bess-office

This file lists every modeling assumption of the two dispatch models: the
rule-based model (RBC, `dispatch_sim.py`) and the LP optimization
(`optimize.py`). It is organized by topic; each section says which model it
applies to.

ID scheme: every assumption has a unique ID per category: `DATA-n` (input data),
`BAT-n` (battery), `TIME-n` (time/foresight), `NET-n` (market and grid) and
`ARCH-n` (model architecture). Numbers are never reused: a new assumption gets
the next free number in its category. When an assumption is corrected, the
correction gets a new ID that refers back to the old one.

This file shows only what currently applies. Replaced assumptions are removed,
so gaps in the numbering (such as DATA-3, DATA-4, NET-1, ARCH-2 and BAT-7) are
expected.

Code comments refer to these IDs, so when you change an assumption here, also
check the matching comment in the code.

---

## Data & reference case

**DATA-1 — Time zone**
- All data (load, PV, prices) is converted to Europe/Amsterdam, not UTC: the
  Liander profile is in local time, and the monthly peak is billed per calendar
  month in local time. Clock changes are handled per source: PV is rounded to
  the hour in UTC before conversion, prices arrive tz-aware from ENTSO-E, and
  the load profile needs a pragmatic fix (DATA-6).

**DATA-2 — Resolution**
- Quarter-hour, because the monthly peak is billed on the highest quarter-hour.
  PV (hourly from PVGIS) is interpolated linearly to quarter-hours rather than
  averaging the load to hours, so the quarter-hour peak is preserved. Prices
  (hourly in 2023, before the 15-minute market of October 2025) are held
  constant within each hour.

**DATA-5 — PV data (PVGIS)**
- Hourly resolution: short cloud transients within the hour are not represented.
  Together with the smoothed load profile (DATA-7), the model sees fewer and
  milder short-term net-load peaks than a real building.
- PVGIS's default shading model uses an elevation map: it sees hills, but not
  buildings. Shading from taller neighbouring buildings is not included, so PV
  yield may be overestimated.
- Mounting is modeled as free-standing. PVGIS only offers free-standing or
  building-integrated; panels on a low frame on a flat roof are in between,
  with less airflow than free-standing, so PV yield may be slightly
  overestimated.

**DATA-6 — Load data (Liander K&O profile)**
- Liander's own standard profile for offices, built from telemetry of large
  consumers and used by Liander to estimate new large-consumer connections
  (source: Liander, "MOOI EIGEN SBI-profielen"). It is a normalized shape, not
  a measurement of one building; the absolute level comes from the scaling in
  DATA-8. This matches the modeled building: at that scale its peak (99.4 kW)
  is well above the large-consumer threshold.
- Because it is a normalized 365 × 96 profile without real clock changes, it
  is made tz-aware pragmatically: the missing hour in March is shifted forward
  (duplicates dropped), and the double hour in October is assigned to summer
  time. Prices and PV, which are real time series, are converted exactly,
  including the clock changes (DATA-1).

**DATA-7 — Load profile smoothing**
- The Liander K&O profile averages many buildings, and their peaks do not
  coincide, so the curve is smoother than that of any single building. A real
  building with the same annual consumption has higher, sharper peaks. Two
  consequences: the 99.4 kW peak (DATA-8) is lower than a real building's, and
  the value of peak reduction is probably underestimated. Real peaks are,
  however, short and erratic, so in practice they are harder to predict and to
  eliminate than here with perfect foresight (TIME-2).

**DATA-8 — Reference building, large-consumer scale**
- Hypothetical reference building, not a real site: a 4,500 m² office at
  115 kWh/m²/year (Dutch average for offices, range 100–150) gives
  517.5 MWh/year. The area is chosen so that the peak lands well above the
  large-consumer threshold (3x80A, ~55 kVA) instead of right at it.
- Peak: scaling the profile to this annual total gives 24.85 kWh in the
  busiest quarter-hour, i.e. 99.4 kW
  (517,500 kWh / profile sum 20,824.42 = 24.85 kWh per quarter-hour).
- The peak is derived from area and intensity in code
  (`derive_peak_kwh_per_quarter`), not set separately, so the two cannot drift
  apart.

**DATA-9 — Battery, BOLT-241**
- Boltainer BOLT-241 (Dutch manufacturer, LFP): 241 kWh, power options
  49/60/99/120 kW. 99 kW chosen to match the 99.4 kW peak (DATA-8), so the
  battery could in principle cover the full peak. Capacity is about 17% of the
  average daily consumption (1,418 kWh/day); no further sizing optimization was
  done.
- Round-trip efficiency and usable SoC range are not stated in the datasheet.
  The model uses typical LFP values: 90% round-trip and SoC 10–95%. Price and
  availability are not verified. Manufacturer cycle life: ≥ 6,000 cycles,
  without stated test conditions (see BAT-3).

**DATA-10 — PV sizing**
- 190 kWp (~409 panels of 465 Wp, ~740 m² of panel area), producing
  186.6 MWh/year: about 36% of annual consumption.
- Two reasons for this size rather than covering the full annual consumption
  (~670 kWp, ~2,600 m² of panels):
  - Roof area: 190 kWp needs ~740 m² of panels, which fits on the roof of a
    multi-storey 4,500 m² office. Full coverage (~2,600 m²) would need a roof
    of more than half the total floor area, i.e. a building of at most one or
    two floors.
  - Export value: for large consumers, exported energy is worth less than
    self-consumed energy (no net metering, no avoided transport and tax, see
    ARCH-5). At 190 kWp, 78% of PV production is consumed on site even without
    a battery; a larger system would mainly add low-value export.
- Not optimized: the PV size was not optimized together with the battery.

---

## Battery (both models)

Both models use the same battery model.

- **BAT-1** — Symmetric power: the same power limit (`power_kw`) for charging
  and discharging. A simplification.
- **BAT-2** — Losses only on charging: the full round-trip efficiency is
  applied when charging, discharging is lossless.
- **BAT-3** — No degradation: capacity and efficiency stay constant over the
  year, and battery wear has no cost in the LP objective (charging losses and
  grid costs of cycling are included).
  - Why it matters: the LP cycles far more than the RBC (equivalent full
    cycles per year, 2023: RBC 102, LP scenario A 487, LP scenario B 264), so
    free wear favours the LP. Its savings are optimistic on this count as
    well as on perfect foresight (TIME-2).
  - What drives wear here: at low C-rates (this system: 99 kW / 241 kWh ≈
    0.41C), ageing is driven mainly by time, temperature and energy throughput,
    and hardly by depth of discharge (Wang et al., 2011, on LFP cells). The
    right correction is therefore a cost per kWh of throughput, not a
    depth-of-discharge cost.
  - Open question: how large that cost should be depends on how calendar and
    cycle ageing combine. If the battery is replaced at the end of its calendar
    life anyway, extra cycles cost little: 487 cycles per year still reaches
    ≥ 6,000 cycles (DATA-9) only after ~12 years. If both add up, every cycle
    shortens the battery's life and the cost per kWh is substantial.
  - Not yet implemented; planned as a sensitivity analysis over a range of
    throughput costs.
- **BAT-4** — No minimum on/off time: the battery can switch every
  quarter-hour.
- **BAT-5** — Efficiency and capacity are constant, regardless of SoC, charging
  rate or temperature.
- **BAT-6** — No self-discharge.

---

## Market & grid (both models)

Both models are costed with the same formula (`compute_financial_metrics` in
`main.py`), which matches the LP objective.

- **NET-2** — Peak reduction only targets import peaks, not export peaks.
- **NET-3** — Unlimited feed-in: no export limit or curtailment.
- **NET-4** — Monthly peak tariff: each month, the highest quarter-hour import
  is billed per kW. Each model handles it differently:
  - LP: one peak variable per calendar month; with perfect foresight it picks
    the lowest achievable peak for each month.
  - RBC: one discharge threshold for the whole year. It is chosen by running
    the RBC for every threshold from 50 to 98 kW (steps of 2 kW,
    `select_rbc_threshold`) and keeping the one with the lowest annual net cost
    (2023: 52 kW). The rule itself never looks at prices (ARCH-1); only this
    choice does.
  - The threshold is chosen on the same year it is tested on (in-sample), with
    hindsight a real controller would not have. This favours the RBC slightly.
- **NET-5** — Energy tax (energiebelasting) at a fixed rate per imported kWh:
  €0.03735, the marginal bracket 50,000–10 million kWh, 2026 rate excl. VAT,
  applied to 2023 prices. Only on import, no net metering (saldering) for large
  consumers. The higher rates on the first 50,000 kWh are paid in every
  scenario, with or without battery, so they do not affect the savings; absolute
  net costs are understated.
- **NET-6** — Scenario B: a hypothetical double energy tax on storage, an extra
  €0.03735 per kWh charged into the battery (default 0, scenario A). The debate
  about double taxation of storage currently concerns small-consumer
  connections; for standalone large-consumer connections an exemption applies
  since 2022. Scenario B is therefore a stress test, not current policy for
  this building, and an upper bound: PV charging is taxed too, whereas
  self-generated, stored and self-consumed electricity is not taxed in reality.
  The LP is re-solved for B; the RBC dispatch is price-agnostic and stays the
  same, only its costs are recalculated.
- **NET-7** — Dynamic (day-ahead) energy contract: all import and export is
  settled at the hourly day-ahead price. This is the logical contract for a
  building that uses its battery for arbitrage, and applies equally to the
  no-battery reference, so the savings isolate the battery's effect. Not
  modeled: (a) the supplier's markup on a dynamic contract, (b) the price risk
  of a dynamic versus a fixed contract on the full building load, which is part
  of the owner's decision but not of the battery's value, and (c) batteries
  installed only for peak shaving or congestion behind a fixed-price contract:
  there the ~€6,600 arbitrage component of the LP savings does not apply.
- **NET-8** — Only the monthly peak component of the grid tariff is modeled.
  The annual contracted capacity (GTV, "kW contract") is treated as a fixed
  cost; exceeding it, which raises the GTV for the whole year, is not modeled.
  Tariff figures are estimates, not verified against the Liander tariff sheet.
- **ARCH-5** — Symmetric import and export prices: export is valued at the
  full day-ahead price. In reality, export misses the avoided transport tariff
  and energy tax, and large consumers are usually paid below the import price
  for feed-in (no net metering). This overvalues export, and therefore larger
  PV systems (DATA-10). A correction needs a real feed-in contract figure.

---

## Rule-based model (`dispatch_sim.py`)

- **TIME-1** — No look-ahead: purely reactive, each quarter-hour on its own.
  Inherent to a rule, not something to be fixed.
- **ARCH-1** — No prices in the model: a physical energy-flow simulation; the
  costs are calculated afterwards in `main.py`.
- **ARCH-3** — Grid charging allowed, corrects ARCH-2. Rule: as long as import
  stays below the threshold, charge from the grid with at most the remaining
  headroom up to the threshold, limited by power (minus what is already charged
  from PV) and max SoC. Side effect: self-consumption drops (2023, threshold
  52 kW: 83.1% without vs. 78.6% with grid charging; 78.3% without battery),
  because the battery is more often full when PV surplus arrives. Peak shaving
  and self-consumption compete for the same SoC, and the threshold makes that
  trade-off implicitly. At the same threshold, the RBC with grid charging is
  also slightly more expensive (€63,558 vs. €63,300). In the LP, grid charging
  is free: the solver decides.

---

## LP optimization (`optimize.py`)

- **TIME-2** — Perfect foresight over the full year: the LP result is an upper
  bound on what a real controller could achieve.
- **ARCH-4** — Costs sit directly in the objective; there is no separate
  financial layer.
- **BAT-8** — Simultaneous charging and discharging is not excluded. Excluding
  it requires binary variables, which would turn the LP into a MILP: much
  slower over 35,040 quarter-hours, and without a guaranteed global optimum in
  practical time.
  - Why it happens: at negative prices, wasting energy through charging losses
    earns money, so charging and discharging at the same time is optimal for
    the LP.
  - Checked (2023 data), scenario A: 399 of 35,032 quarter-hours, all at a
    negative price (1,256 quarter-hours < 0). 546 kWh is lost, at most
    ~€270/year even at the lowest price (−500 EUR/MWh): ~3% of the LP savings.
    Scenario B: 16 quarter-hours, also all at a negative price.
  - The effect is small and reported, so the model stays an LP.
- **BAT-9** — End SoC ≥ initial SoC at the end of the year. Without this, the
  LP drains the battery for free at the end and counts that energy as savings.
  The RBC has no such condition (2023: ends at 208.8 kWh vs. 120.5 kWh at the
  start, a small disadvantage for the RBC).

---

## Context, not an assumption

If the building is in a grid-congested area, the battery may qualify for the
Flex-e subsidy (RVO), which covers up to 40% of the investment for large
consumers (2026 conditions). At 99 kW it falls in the group below 100 kW,
which does not require a congestion management contract with the grid
operator; the 100 kW limit refers to the power of the measure, not of the
connection. Investment costs and subsidies are not yet in the model.