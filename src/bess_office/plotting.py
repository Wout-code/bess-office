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


def _eur(value: float, _pos=None) -> str:
    return f"€{value / 1000:.0f}k"


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
        If True, also open the figure in a window after saving. The call then
        waits until the window is closed. Without a display (e.g. on a server)
        matplotlib falls back to a non-interactive backend and only warns.

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

    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    ax.set_xticks(list(x), labels, color=TEXT_PRIMARY)
    ax.yaxis.set_major_formatter(FuncFormatter(_eur))
    ax.tick_params(axis="y", colors=TEXT_SECONDARY)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_visible(False)
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

    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    if show:
        plt.show()
    plt.close(fig)
    return path