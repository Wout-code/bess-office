"""Plots for the bess-office results."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Categorical colours in fixed order (dataviz reference palette, light mode).
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# (key in compute_financial_metrics, label, colour). Order = stacking order.
COST_COMPONENTS = [
    ("import_cost_eur", "Energy (day-ahead)", "#2a78d6"),
    ("energy_tax_cost_eur", "Energy tax", "#eb6834"),
    ("transport_cost_eur", "Transport", "#1baf7a"),
    ("peak_cost_eur", "Monthly peak", "#eda100"),
]
EXPORT_COMPONENT = ("export_revenue_eur", "Export revenue (subtracted)", "#e87ba4")

# (key, label) per component for the savings chart, in display order. Export is
# a revenue, so its saving has the opposite sign of the cost components.
SAVINGS_COMPONENTS = [
    ("import_cost_eur", "Energy\n(day-ahead)"),
    ("energy_tax_cost_eur", "Energy tax"),
    ("transport_cost_eur", "Transport"),
    ("peak_cost_eur", "Monthly peak"),
    ("export_revenue_eur", "Export\nrevenue"),
]
SCENARIO_COLOURS = ["#8e8c86", "#2a78d6"]  # first scenario grey, second blue


def _eur(value: float, _pos=None) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}€{abs(value) / 1000:.0f}k"


def _style_axes(ax) -> None:
    """Shared axis styling: light grid, no frame, euro formatting on y."""
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.tick_params(axis="y", colors=TEXT_SECONDARY)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)


def _save(fig, path: Path, show: bool) -> Path:
    """Save the figure; keep it open only if main.py will show it."""
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    if not show:
        plt.close(fig)
    return path


def plot_cost_breakdown(financials: dict[str, dict], path: Path, show: bool = True) -> Path:
    """
    Stacked bar chart of annual cost per component, one bar per scenario.

    Parameters
    ----------
    financials : dict[str, dict]
        Scenario label -> output of main.compute_financial_metrics.
        Insertion order is the bar order.
    path : Path
        Output PNG path; parent directories are created if needed.
    show : bool
        If True, keep the figure open so main.py can show it with plt.show();
        otherwise close it after saving.

    Returns
    -------
    Path
        The path written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = list(financials)
    x = range(len(labels))
    width = 0.55

    fig, ax = plt.subplots(figsize=(8, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # Costs stacked above zero; a 2 px surface-coloured edge separates the segments.
    bottoms = [0.0] * len(labels)
    for key, label, color in COST_COMPONENTS:
        values = [financials[s][key] for s in labels]
        ax.bar(x, values, width, bottom=bottoms, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        bottoms = [b + v for b, v in zip(bottoms, values)]

    # Export as a deduction: negative segment below the zero line.
    key, label, color = EXPORT_COMPONENT
    exports = [-financials[s][key] for s in labels]
    ax.bar(x, exports, width, color=color, label=label, edgecolor=SURFACE, linewidth=2)

    # Net cost as a number above the bar.
    for i, s in enumerate(labels):
        net = financials[s]["net_cost_eur"]
        ax.annotate(
            f"net €{net:,.0f}",
            xy=(i, bottoms[i]),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=TEXT_PRIMARY,
        )

    _style_axes(ax)
    ax.set_xticks(list(x), labels, color=TEXT_PRIMARY)
    ax.set_ylim(min(exports) * 1.6, max(bottoms) * 1.12)

    ax.set_ylabel("EUR per year", color=TEXT_SECONDARY)
    ax.set_title(
        "Annual cost per component, scenario A\n(2023 prices and PV, 2026 tariffs)",
        color=TEXT_PRIMARY,
        loc="left",
        fontsize=12,
    )
    # Legend in the same order as the stack from top to bottom:
    # cost components reversed, export (below zero) last.
    handles, legend_labels = ax.get_legend_handles_labels()
    order = list(range(len(COST_COMPONENTS)))[::-1] + [len(COST_COMPONENTS)]
    ax.legend(
        [handles[i] for i in order],
        [legend_labels[i] for i in order],
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(1.0, 1.0),
        labelcolor=TEXT_PRIMARY,
    )

    return _save(fig, path, show)


def plot_savings_breakdown(
    reference: dict, scenarios: dict[str, dict], path: Path, show: bool = True
) -> Path:
    """
    Grouped bar chart of the annual saving per cost component versus a
    reference (no battery), one bar per scenario.

    Parameters
    ----------
    reference : dict
        Output of main.compute_financial_metrics for the no-battery case.
    scenarios : dict[str, dict]
        Scenario label -> output of main.compute_financial_metrics.
        Insertion order is the bar order within each group.
    path : Path
        Output PNG path; parent directories are created if needed.
    show : bool
        If True, keep the figure open so main.py can show it with plt.show();
        otherwise close it after saving.

    Returns
    -------
    Path
        The path written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    labels = list(scenarios)
    n = len(labels)
    width = 0.8 / n
    x = range(len(SAVINGS_COMPONENTS))

    fig, ax = plt.subplots(figsize=(8, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    for j, (label, colour) in enumerate(zip(labels, SCENARIO_COLOURS)):
        fin = scenarios[label]
        savings = []
        for key, _ in SAVINGS_COMPONENTS:
            if key == "export_revenue_eur":
                savings.append(fin[key] - reference[key])  # more export revenue = saving
            else:
                savings.append(reference[key] - fin[key])  # lower cost = saving
        total = reference["net_cost_eur"] - fin["net_cost_eur"]
        offsets = [i + (j - (n - 1) / 2) * width for i in x]
        bars = ax.bar(
            offsets, savings, width, color=colour, edgecolor=SURFACE, linewidth=2,
            label=f"{label}: total €{total:,.0f}/year",
        )
        for bar, value in zip(bars, savings):
            ax.annotate(
                f"{'−' if value < 0 else ''}€{abs(value) / 1000:.1f}k",
                xy=(bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 4 if value >= 0 else -4),
                textcoords="offset points",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=9,
                color=TEXT_PRIMARY,
            )

    _style_axes(ax)
    ax.set_xticks(list(x), [lbl for _, lbl in SAVINGS_COMPONENTS], color=TEXT_PRIMARY)

    ax.set_ylabel("Saving vs. no battery, EUR per year", color=TEXT_SECONDARY)
    ax.set_title(
        "Where the savings come from, scenario A\n(2023 prices and PV, 2026 tariffs)",
        color=TEXT_PRIMARY,
        loc="left",
        fontsize=12,
    )
    ax.legend(frameon=False, loc="upper right", labelcolor=TEXT_PRIMARY)

    return _save(fig, path, show)