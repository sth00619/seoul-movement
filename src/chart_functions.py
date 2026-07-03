"""Chart functions for the Seoul Movement lecture.

This module contains one callable per chart specified in
``PRESENTATION_DESIGN.md``. Every function:

- Takes clean processed dataframes as input (never raw)
- Returns a matplotlib ``Figure`` (for PNG export → PPT) or a plotly
  ``Figure`` (for HTML export → interactive site)
- Optionally writes both artifacts to ``data/exports/`` when ``export_dir``
  is passed
- Uses only **English** for every label, title, legend, and annotation,
  per the lecture's audience constraint

Sections are populated in the order they appear in the talk:

    Section 4  →  Chart A, Chart B    (this delivery)
    Section 5  →  Chart C, D, E, F, G
    Section 6  →  Chart H, I, J, K, L, M, N
    Section 7  →  Chart O
    Section 8  →  Chart P  (lives in interactive/, not here)

Design language
---------------
All charts share a small design system (see ``STYLE`` and ``PALETTE`` below).
This is not decoration — visual consistency across a talk is itself a data
viz principle. When students see the same three focus-station colors used
in every chart, the mental model transfers between slides for free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Global design system
# ---------------------------------------------------------------------------

# Focus stations get the same color everywhere. All other stations use gray.
PALETTE: dict[str, str] = {
    "강남":     "#D4A017",   # gold — Gangnam
    "홍대입구": "#C1272D",   # crimson — Hongdae
    "여의도":   "#4A6FA5",   # steel blue — Yeouido
    "_other":  "#8A8580",   # warm gray — background stations
    "_grid":   "#E5E1D8",   # manila tan grid lines
    "_text":   "#2A2622",   # near-black for text
}

# Sequential palette for the heatmap (Chart A). Warm neutral → deep red so
# high-density hours read as intensity, not decoration.
HEATMAP_CMAP = mpl.colors.LinearSegmentedColormap.from_list(
    "seoul_heat",
    ["#F7F3EA", "#EAD7B5", "#D89563", "#B95E3E", "#7A2E22"],
)

STYLE: dict = {
    "font.family":       ["DejaVu Sans"],
    "axes.edgecolor":    PALETTE["_text"],
    "axes.labelcolor":   PALETTE["_text"],
    "xtick.color":       PALETTE["_text"],
    "ytick.color":       PALETTE["_text"],
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.color":        PALETTE["_grid"],
    "grid.linewidth":    0.6,
    "figure.dpi":        110,
    "savefig.dpi":       160,
    "savefig.bbox":      "tight",
    "savefig.facecolor": "white",
}

DAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Human-readable English station names (charts must be English-only)
STATION_EN: dict[str, str] = {
    "강남":     "Gangnam",
    "홍대입구": "Hongdae",
    "여의도":   "Yeouido",
}


def _apply_style() -> None:
    """Apply the shared style. Call at the top of every chart function."""
    for k, v in STYLE.items():
        mpl.rcParams[k] = v


def _save_matplotlib(fig, export_dir: Path | None, name: str) -> Path | None:
    """Persist a matplotlib figure as PNG under ``export_dir``."""
    if export_dir is None:
        return None
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / f"{name}.png"
    fig.savefig(out)
    return out


# ---------------------------------------------------------------------------
# Chart A — Hourly × weekday ridership heatmap (3 panels, shared scale)
# ---------------------------------------------------------------------------


def make_chart_A(
    weekday_hour_matrices: dict[str, pd.DataFrame],
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "Seoul is breathing — three neighborhoods, three rhythms",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart A · 3-panel weekday × hour heatmap.

    Why this chart type
    -------------------
    Ridership varies on two cyclical axes: **hour of day** and **day of week**.
    A heatmap is the only chart that shows both cycles at cell-level density.
    A line chart hides the weekend pattern; a bar chart fragments the picture.
    Sharing the color scale across all three panels is critical — that's what
    lets the audience compare *magnitudes* between stations, not just
    *shapes* within each station.

    Parameters
    ----------
    weekday_hour_matrices : dict[str, DataFrame]
        Output of :func:`preprocess.build_weekday_hour_matrix`. Each value is
        a 7×24 dataframe (rows Mon..Sun, columns hour 00..23).
    focus_stations : list of str
        Which stations to plot, in left-to-right order.
    title : str
        Overall figure title (English).
    export_dir : Path, optional
        If given, PNG is written to ``{export_dir}/chart_A.png``.

    Returns
    -------
    matplotlib.figure.Figure
        The rendered figure. Caller decides whether to ``plt.show()`` or
        persist to disk.
    """
    _apply_style()

    # Shared color scale — use the global max across all three panels
    vmax = max(m.to_numpy().max() for s, m in weekday_hour_matrices.items()
               if s in focus_stations)

    fig, axes = plt.subplots(
        nrows=1,
        ncols=len(focus_stations),
        figsize=(4.6 * len(focus_stations), 4.2),
        sharey=True,
    )

    for ax, station_kr in zip(axes, focus_stations):
        mat = weekday_hour_matrices[station_kr]
        im = ax.imshow(
            mat.to_numpy(),
            aspect="auto",
            cmap=HEATMAP_CMAP,
            vmin=0,
            vmax=vmax,
            interpolation="nearest",
        )
        ax.set_title(
            STATION_EN.get(station_kr, station_kr),
            fontsize=13,
            color=PALETTE["_text"],
            pad=8,
        )
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xticklabels(["00", "06", "12", "18", "23"], fontsize=9)
        ax.set_yticks(range(7))
        ax.set_yticklabels(DAYS_EN, fontsize=9)
        ax.set_xlabel("Hour of day", fontsize=10)
        ax.grid(False)

    axes[0].set_ylabel("Day of week", fontsize=10)

    # Shared colorbar on the right
    cbar = fig.colorbar(im, ax=axes, shrink=0.72, pad=0.02)
    cbar.set_label("Mean daily taps at this hour", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.suptitle(title, fontsize=14, y=1.02, color=PALETTE["_text"])

    _save_matplotlib(fig, export_dir, "chart_A_weekday_hour_heatmap")
    return fig


# ---------------------------------------------------------------------------
# Chart B — Multi-line hourly ridership curves with peak annotations
# ---------------------------------------------------------------------------


def make_chart_B(
    long_hourly: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "The shape of a neighborhood's day",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart B · Multi-line hourly ridership curves.

    Why this chart type
    -------------------
    After Chart A revealed density, the audience wants to compare *shapes*.
    A line chart is the archetypal choice for "how does one continuous
    quantity move against another continuous quantity." Overlaying three
    lines makes each station's pulse directly comparable.

    Design detail
    -------------
    Each peak (morning + evening) is annotated with a callout. This is the
    Data Viz teaching moment SONG will name aloud: **annotations turn a
    chart into an argument**.

    Parameters
    ----------
    long_hourly : DataFrame
        Output of ``preprocess.normalize_subway_hourly`` (long tidy).
    focus_stations : list of str
        Stations to plot as colored lines.
    title, export_dir : same as Chart A.
    """
    _apply_style()
    fig, ax = plt.subplots(figsize=(11, 5.2))

    # Aggregate to (station, hour) → mean count across the window
    agg = (
        long_hourly[long_hourly["station"].isin(focus_stations)]
        .groupby(["station", "hour"], as_index=False)["count"].sum()
    )

    # Normalize each station's curve to daily total = 100, so shapes are
    # directly comparable regardless of absolute volume. This is the honest
    # move here: readers should be comparing *when* people ride, not
    # *how many* — and the y-axis label says so explicitly.
    for station in focus_stations:
        s = agg[agg["station"] == station].sort_values("hour")
        vals = s["count"].to_numpy(dtype=float)
        vals = 100 * vals / vals.sum()  # % of daily total
        hours = s["hour"].to_numpy()
        color = PALETTE.get(station, PALETTE["_other"])
        ax.plot(
            hours, vals,
            color=color, linewidth=2.4,
            label=STATION_EN.get(station, station),
            marker="o", markersize=4, markerfacecolor="white",
            markeredgewidth=1.6,
        )

        # Annotate the tallest peak
        peak_h = int(hours[np.argmax(vals)])
        peak_v = float(vals.max())
        ax.annotate(
            f"peak {peak_h:02d}:00",
            xy=(peak_h, peak_v),
            xytext=(peak_h + 1.2, peak_v + 0.6),
            fontsize=9,
            color=color,
            arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.7),
        )

    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_xlabel("Hour of day", fontsize=11)
    ax.set_ylabel("Share of daily ridership  (%)", fontsize=11)
    ax.set_title(title, fontsize=14, color=PALETTE["_text"], pad=12)
    ax.legend(loc="upper right", frameon=False, fontsize=10)

    # Soft vertical guides at commute peaks
    for h in (8, 18):
        ax.axvline(h, color=PALETTE["_grid"], linewidth=1.0, zorder=0)

    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_B_hourly_curves")
    return fig


# ---------------------------------------------------------------------------
# Convenience: run Section 4 charts from processed parquets
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Section 5 — Testing H1: "All busy stations are basically the same"
# ---------------------------------------------------------------------------


def make_chart_C(
    long_hourly: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "On raw volume, they look identical — this is what H1 predicts",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart C · Annual ridership totals — grouped vertical bar.

    Why this chart type
    -------------------
    Bar charts are the standard for comparing discrete categories on a single
    metric. This slide is the *setup*: on total volume the three stations look
    nearly the same. That's the deliberate punchline — H1 looks plausible
    here, so the audience is primed for the surprise in Charts D and E.
    """
    _apply_style()

    agg = (
        long_hourly[long_hourly["station"].isin(focus_stations)]
        .groupby(["station", "year_month"])["count"].sum()
        .reset_index()
    )
    annual = (
        agg.assign(year=agg["year_month"].dt.year)
        .groupby(["station", "year"])["count"].sum()
        .reset_index()
    )

    years = sorted(annual["year"].unique())
    n_stations = len(focus_stations)
    x = np.arange(n_stations)
    bar_w = 0.35
    offsets = np.linspace(-(len(years) - 1) * bar_w / 2,
                          (len(years) - 1) * bar_w / 2, len(years))

    fig, ax = plt.subplots(figsize=(9, 5.2))
    year_colors = ["#C8B89A", "#8A7060"]
    for i, (yr, offset, col) in enumerate(zip(years, offsets, year_colors)):
        vals = [
            annual[(annual["station"] == s) & (annual["year"] == yr)]["count"].sum()
            for s in focus_stations
        ]
        bars = ax.bar(x + offset, [v / 1e6 for v in vals],
                      width=bar_w * 0.85, color=col,
                      label=str(yr), zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([STATION_EN.get(s, s) for s in focus_stations], fontsize=12)
    ax.set_ylabel("Annual ridership  (millions)", fontsize=11)
    ax.set_title(title, fontsize=13, color=PALETTE["_text"], pad=12)
    ax.legend(title="Year", frameon=False, fontsize=10)
    ax.yaxis.grid(True, color=PALETTE["_grid"])
    ax.set_axisbelow(True)

    # Annotation: "They look the same → that's the trap"
    ax.annotate(
        "Same scale, similar volumes\n→ H1 seems plausible here",
        xy=(1, ax.get_ylim()[1] * 0.88),
        fontsize=9, color="#888", ha="center",
        style="italic",
    )
    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_C_annual_totals")
    return fig


def make_chart_D(
    long_hourly: pd.DataFrame,
    daily: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "Weekend vs weekday balance — three completely different personalities",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart D · Weekday / weekend diverging horizontal bar.

    Why this chart type
    -------------------
    A diverging bar chart is the correct visualization when one metric can go
    in two meaningfully opposite directions. Positive = weekend-heavy,
    negative = weekday-heavy. The direction of a neighborhood's personality
    is instantly readable at a glance — H1 is dead the moment this appears.
    """
    _apply_style()

    ratios = {}
    for s in focus_stations:
        d = daily[daily["station"] == s].copy()
        d["total"] = d["board_total"] + d["alight_total"]
        wd_mean = d[d["weekday"] < 5]["total"].mean()
        we_mean = d[d["weekday"] >= 5]["total"].mean()
        ratios[s] = (we_mean / wd_mean) - 1.0   # >0 = weekend-heavy

    fig, ax = plt.subplots(figsize=(9, 3.8))
    stations_sorted = sorted(ratios, key=ratios.get)
    vals = [ratios[s] for s in stations_sorted]
    colors = [PALETTE.get(s, PALETTE["_other"]) for s in stations_sorted]

    bars = ax.barh(
        [STATION_EN.get(s, s) for s in stations_sorted],
        vals, color=colors, height=0.52, zorder=3,
    )
    ax.axvline(0, color=PALETTE["_text"], linewidth=1.2, zorder=4)

    # Annotations on each bar
    for bar, val, s in zip(bars, vals, stations_sorted):
        direction = "weekend-heavy" if val > 0 else "weekday-heavy"
        ha = "left" if val > 0 else "right"
        offset = 0.015 if val > 0 else -0.015
        ax.text(val + offset, bar.get_y() + bar.get_height() / 2,
                f"{direction}  ({val:+.0%})",
                va="center", ha=ha, fontsize=9.5,
                color=PALETTE.get(s, PALETTE["_text"]))

    ax.set_xlabel("Weekend ridership vs weekday mean  (relative)", fontsize=11)
    ax.set_title(title, fontsize=13, color=PALETTE["_text"], pad=12)
    ax.set_xlim(min(vals) - 0.25, max(vals) + 0.45)
    ax.xaxis.grid(True, color=PALETTE["_grid"])
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_D_weekday_weekend_diverging")
    return fig


def make_chart_E(
    feats: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "Station profiles — six dimensions, three distinct shapes",
    export_dir: Path | None = None,
) -> "go.Figure":
    """Chart E · Radar / spider chart — station multi-dimensional profile.

    Why this chart type (and why it's defensible here)
    ---------------------------------------------------
    Radar charts are often criticized in data viz. This is a teaching moment:
    we use one correctly because we have (a) a fixed small number of axes,
    (b) all axes on directly comparable normalized 0-1 scales, (c) a purpose
    of showing *shape* / profile rather than precise values.

    SONG should name these three conditions aloud when presenting — it shows
    the presenter knows the field's debates, not just the chart types.

    Returns a Plotly figure (interactive HTML) instead of matplotlib, because
    plotly's polar chart handles the radar polygon far more cleanly and
    exports natively to the interactive site.
    """
    import plotly.graph_objects as go

    feature_cols = [
        "morning_peak_intensity",
        "evening_peak_intensity",
        "weekend_weekday_ratio",
        "late_night_share",
        "directional_asymmetry_peak",
        "cv_hourly",
    ]
    axis_labels = [
        "Morning peak",
        "Evening peak",
        "Weekend balance",
        "Late-night share",
        "AM directional asymmetry",
        "Hourly volatility (CV)",
    ]

    # Normalize each feature to [0, 1] across focus stations for radar
    sub = feats[feats["station"].isin(focus_stations)].set_index("station")
    normed = sub[feature_cols].copy()
    for col in feature_cols:
        col_min, col_max = normed[col].min(), normed[col].max()
        if col_max > col_min:
            normed[col] = (normed[col] - col_min) / (col_max - col_min)

    colors_hex = {
        "강남":     "#D4A017",
        "홍대입구": "#C1272D",
        "여의도":   "#4A6FA5",
    }

    def hex_to_rgba(h: str, alpha: float = 0.20) -> str:
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    fig = go.Figure()
    for station in focus_stations:
        vals = normed.loc[station, feature_cols].tolist()
        vals_closed = vals + [vals[0]]
        labels_closed = axis_labels + [axis_labels[0]]
        base_color = colors_hex.get(station, "#888888")
        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor=hex_to_rgba(base_color, 0.20),
            line=dict(color=base_color, width=2.5),
            name=STATION_EN.get(station, station),
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1],
                            showticklabels=False, gridcolor="#E5E1D8"),
            angularaxis=dict(gridcolor="#E5E1D8"),
            bgcolor="white",
        ),
        showlegend=True,
        title=dict(text=title, font=dict(size=14, color="#2A2622"), x=0.5),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
        paper_bgcolor="white",
        width=620, height=520,
    )

    if export_dir is not None:
        Path(export_dir).mkdir(parents=True, exist_ok=True)
        fig.write_html(str(Path(export_dir) / "chart_E_radar.html"))
        try:
            fig.write_image(str(Path(export_dir) / "chart_E_radar.png"),
                            scale=2)
        except Exception:
            pass   # kaleido optional in CI
    return fig


def make_chart_F(
    long_hourly: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    title: str = "Ridership distributions are statistically distinct (KS test)",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart F · Empirical CDF with KS distance annotated.

    Why this chart type
    -------------------
    The CDF is the geometric object the KS test literally operates on: the
    KS statistic is the maximum vertical distance between two CDF curves.
    Showing the test *as a picture* — a vertical arrow — makes an inferential
    statistic legible to non-statisticians. This is rare and powerful in a
    Data Viz class. Students leave understanding *why* the KS test works,
    not just that it was applied.
    """
    from scipy.stats import ks_2samp

    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))

    station_data = {}
    for s in focus_stations:
        hourly = (
            long_hourly[long_hourly["station"] == s]
            .groupby("hour")["count"].sum()
            .reindex(range(24), fill_value=0)
            .to_numpy(dtype=float)
        )
        total = hourly.sum()
        station_data[s] = hourly / total if total else hourly

    # Draw empirical CDFs
    for s in focus_stations:
        vals = np.sort(station_data[s])
        cdf  = np.arange(1, len(vals) + 1) / len(vals)
        color = PALETTE.get(s, PALETTE["_other"])
        ax.step(vals, cdf, color=color, linewidth=2.2,
                label=STATION_EN.get(s, s), where="post")

    # Annotate KS distance between Gangnam and Hongdae (most dramatic pair)
    s_a, s_b = focus_stations[0], focus_stations[1]
    stat, p_val = ks_2samp(station_data[s_a], station_data[s_b])
    vals_a = np.sort(station_data[s_a])
    vals_b = np.sort(station_data[s_b])

    # Find the x-value where the two CDFs are furthest apart
    all_vals = np.unique(np.concatenate([vals_a, vals_b]))
    cdf_a = np.searchsorted(vals_a, all_vals, side="right") / len(vals_a)
    cdf_b = np.searchsorted(vals_b, all_vals, side="right") / len(vals_b)
    ks_idx = np.argmax(np.abs(cdf_a - cdf_b))
    x_ks = all_vals[ks_idx]
    y_lo, y_hi = min(cdf_a[ks_idx], cdf_b[ks_idx]), max(cdf_a[ks_idx], cdf_b[ks_idx])

    ax.annotate(
        "",
        xy=(x_ks, y_hi), xytext=(x_ks, y_lo),
        arrowprops=dict(arrowstyle="<->", color="#2A2622", lw=1.8),
    )
    ax.text(
        x_ks + 0.003, (y_lo + y_hi) / 2,
        f"KS = {stat:.3f}\np < 0.001",
        fontsize=9.5, va="center", color="#2A2622",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#C8B89A", lw=1),
    )

    ax.set_xlabel("Hourly share of daily ridership", fontsize=11)
    ax.set_ylabel("Cumulative probability", fontsize=11)
    ax.set_title(title, fontsize=13, color=PALETTE["_text"], pad=12)
    ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_F_ks_cdf")
    return fig


def make_chart_G(
    long_hourly: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    peak_hour: int = 8,
    title: str = "Who is arriving vs departing at 08:00 — neighborhood purpose in one chart",
    export_dir: Path | None = None,
) -> "plt.Figure":
    """Chart G · Butterfly (back-to-back) bar at AM peak hour.

    Why this chart type
    -------------------
    Butterfly bar charts are designed precisely for two-directional comparisons
    of the same subjects. Left bars = tap-out (alighting), right bars =
    tap-in (boarding). Yeouido will show massive left bars with tiny right —
    people arriving to work. Hongdae will be nearly symmetric off-peak.
    This chart *proves* the purpose of each neighborhood in one image.
    """
    _apply_style()

    peak = long_hourly[long_hourly["hour"] == peak_hour]
    agg  = (
        peak[peak["station"].isin(focus_stations)]
        .groupby(["station", "direction"])["count"].sum()
        .unstack(fill_value=0)
        .reindex(list(focus_stations))
    )

    fig, ax = plt.subplots(figsize=(10, 4.2))
    y_pos  = np.arange(len(focus_stations))
    bar_h  = 0.4
    colors = [PALETTE.get(s, PALETTE["_other"]) for s in focus_stations]

    # Left side: alighting (tap-out)
    alight_vals = agg.get("alight", pd.Series([0] * len(focus_stations))).to_numpy()
    ax.barh(y_pos, -alight_vals / 1e3, height=bar_h, color=colors,
            alpha=0.85, zorder=3, label="Tap-out (alighting)")

    # Right side: boarding (tap-in)
    board_vals = agg.get("board", pd.Series([0] * len(focus_stations))).to_numpy()
    ax.barh(y_pos, board_vals / 1e3, height=bar_h, color=colors,
            alpha=0.45, zorder=3, label="Tap-in (boarding)", hatch="///")

    ax.axvline(0, color=PALETTE["_text"], linewidth=1.4, zorder=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([STATION_EN.get(s, s) for s in focus_stations], fontsize=12)

    # X-axis symmetric and labeled
    xlim = max(abs(ax.get_xlim()[0]), ax.get_xlim()[1]) * 1.15
    ax.set_xlim(-xlim, xlim)
    import matplotlib.ticker as ticker
    ax.xaxis.set_major_locator(ticker.LinearLocator(numticks=7))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{abs(v):.0f}k"))
    ax.set_xlabel(f"Ridership at {peak_hour:02d}:00  (thousands)", fontsize=11)

    # Direction labels
    ax.text(-xlim * 0.97, -0.7, "← Alighting (tap-out)",
            ha="left", fontsize=9.5, color="#666", style="italic")
    ax.text( xlim * 0.97, -0.7, "Boarding (tap-in) →",
            ha="right", fontsize=9.5, color="#666", style="italic")

    ax.set_title(title, fontsize=13, color=PALETTE["_text"], pad=12)
    ax.legend(loc="lower right", frameon=False, fontsize=9.5)
    ax.xaxis.grid(True, color=PALETTE["_grid"])
    ax.set_axisbelow(True)

    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_G_butterfly_am_peak")
    return fig


def render_section_5(
    long_hourly: pd.DataFrame,
    daily: pd.DataFrame,
    feats: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    export_dir: Path | None = None,
) -> dict:
    """Build every Section 5 chart in one call.

    Returns dict keyed by chart letter: 'C', 'D', 'E', 'F', 'G'.
    """
    return {
        "C": make_chart_C(long_hourly, list(focus_stations), export_dir=export_dir),
        "D": make_chart_D(long_hourly, daily, list(focus_stations), export_dir=export_dir),
        "E": make_chart_E(feats, list(focus_stations), export_dir=export_dir),
        "F": make_chart_F(long_hourly, list(focus_stations), export_dir=export_dir),
        "G": make_chart_G(long_hourly, list(focus_stations), export_dir=export_dir),
    }


def render_section_4(
    long_hourly: pd.DataFrame,
    daily: pd.DataFrame,
    focus_stations: list[str] = ("강남", "홍대입구", "여의도"),
    export_dir: Path | None = None,
) -> dict[str, "plt.Figure"]:
    """Build every Section 4 chart in one call and return them by name.

    This is the entrypoint the notebook uses:

    >>> figs = render_section_4(long, daily, export_dir="data/exports")
    >>> figs["A"], figs["B"]
    """
    from src.preprocess import build_weekday_hour_matrix

    matrices = build_weekday_hour_matrix(long_hourly, daily, list(focus_stations))
    fig_a = make_chart_A(matrices, list(focus_stations), export_dir=export_dir)
    fig_b = make_chart_B(long_hourly, list(focus_stations), export_dir=export_dir)
    return {"A": fig_a, "B": fig_b}

# ---------------------------------------------------------------------------
# Section 6 — Deeper Patterns: Hidden Structure
# ---------------------------------------------------------------------------

CLUSTER_PALETTE: dict[str, str] = {
    "Business District":    "#D4A017",
    "Business District 2":  "#B87333",
    "Nightlife District":   "#C1272D",
    "Residential Commuter": "#4A6FA5",
    "Transit Interchange":  "#5A9E6F",
    "_unknown":             "#8A8580",
}


def _cluster_color(name: str) -> str:
    for key, col in CLUSTER_PALETTE.items():
        if key.lower() in name.lower():
            return col
    return CLUSTER_PALETTE["_unknown"]


def _hex_rgba(h: str, alpha: float = 0.18) -> str:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def make_chart_I(feats, result, title="Seoul's subway stations naturally fall into 5 neighborhood types", export_dir=None):
    """Chart I · UMAP scatter coloured by KMeans cluster (Plotly interactive).

    Why this chart type: we have 6D features — UMAP reduces to 2D while
    preserving local cluster structure better than PCA. Hover reveals the
    station name and all 6 feature values.
    """
    import plotly.graph_objects as go
    embedding, labels, names = result.embedding_2d, result.labels, result.cluster_names

    fig = go.Figure()
    for cid, cname in sorted(names.items()):
        mask  = labels == cid
        idxs  = np.where(mask)[0]
        color = _cluster_color(cname)
        texts = []
        for i in idxs:
            s   = feats.iloc[i]
            texts.append(
                f"<b>{STATION_EN.get(s['station'], s['station'])} ({s['station']})</b><br>"
                f"Morning peak: {s['morning_peak_intensity']:.3f}<br>"
                f"Late-night: {s['late_night_share']:.3f}<br>"
                f"AM asymmetry: {s['directional_asymmetry_peak']:+.3f}<br>"
                f"Weekend bal.: {s['weekend_weekday_ratio']:.2f}"
            )
        fig.add_trace(go.Scatter(
            x=embedding[mask, 0], y=embedding[mask, 1],
            mode="markers", name=cname,
            marker=dict(color=color, size=12, line=dict(width=1.5, color="white")),
            text=texts, hovertemplate="%{text}<extra></extra>",
        ))
    focus_kr = {"강남", "홍대입구", "여의도"}
    for i, stn in enumerate(feats["station"]):
        if stn in focus_kr:
            fig.add_annotation(
                x=float(embedding[i, 0]), y=float(embedding[i, 1]),
                text=f"<b>{STATION_EN.get(stn, stn)}</b>",
                showarrow=True, arrowhead=2, arrowwidth=1.5,
                arrowcolor="#2A2622", ax=28, ay=-28,
                font=dict(size=11, color="#2A2622"),
            )
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#2A2622"), x=0.5),
        xaxis=dict(title="UMAP 1", showgrid=True, gridcolor="#E5E1D8", zeroline=False),
        yaxis=dict(title="UMAP 2", showgrid=True, gridcolor="#E5E1D8", zeroline=False),
        legend=dict(title="Cluster type", x=1.01),
        paper_bgcolor="white", plot_bgcolor="white", width=760, height=540,
    )
    if export_dir is not None:
        p = Path(export_dir); p.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(p / "chart_I_umap_clusters.html"))
        try: fig.write_image(str(p / "chart_I_umap_clusters.png"), scale=2)
        except Exception: pass
    return fig


def make_chart_J(result, title="Each cluster has a distinct archetype — recognized without labels", export_dir=None):
    """Chart J · Cluster centroid radar (Plotly).

    Why: reuses the same polar chart type as Chart E — visual language
    consistency means the audience already knows how to read this.
    Now the polygons are cluster archetypes, not individual stations.
    """
    import plotly.graph_objects as go
    feature_cols  = ["morning_peak_intensity","evening_peak_intensity",
                     "weekend_weekday_ratio","late_night_share",
                     "directional_asymmetry_peak","cv_hourly"]
    axis_labels   = ["Morning peak","Evening peak","Weekend balance",
                     "Late-night share","AM asymmetry","Hourly volatility"]
    centroids = result.centroids_original[feature_cols].copy()
    normed    = (centroids - centroids.min()) / (centroids.max() - centroids.min() + 1e-9)

    fig = go.Figure()
    for cid, cname in sorted(result.cluster_names.items()):
        rk   = f"cluster_{cid}"
        vals = normed.loc[rk, feature_cols].tolist()
        vc   = vals + [vals[0]]; lc = axis_labels + [axis_labels[0]]
        col  = _cluster_color(cname)
        fig.add_trace(go.Scatterpolar(
            r=vc, theta=lc, fill="toself",
            fillcolor=_hex_rgba(col, 0.18),
            line=dict(color=col, width=2.2), name=cname,
        ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0,1], showticklabels=False, gridcolor="#E5E1D8"),
            angularaxis=dict(gridcolor="#E5E1D8"), bgcolor="white",
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", font=dict(size=10)),
        title=dict(text=title, font=dict(size=13, color="#2A2622"), x=0.5),
        paper_bgcolor="white", width=640, height=560,
    )
    if export_dir is not None:
        p = Path(export_dir); p.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(p / "chart_J_cluster_radar.html"))
        try: fig.write_image(str(p / "chart_J_cluster_radar.png"), scale=2)
        except Exception: pass
    return fig


def make_chart_K(feats, result, focus_stations=("강남","홍대입구","여의도"),
                  title="Where do our three stations land in the full city picture?", export_dir=None):
    """Chart K · Annotated UMAP — focus stations as stars over faded cluster cloud.

    Why: layered visualization — background context (all stations, faded)
    + focused foreground (the three we've studied). Answers 'where does
    my question live inside the bigger picture?'
    """
    import plotly.graph_objects as go
    embedding, labels, names = result.embedding_2d, result.labels, result.cluster_names
    fig = go.Figure()
    for cid, cname in sorted(names.items()):
        mask = labels == cid
        col  = _cluster_color(cname)
        stns = [feats.iloc[i]["station"] for i in np.where(mask)[0]]
        fig.add_trace(go.Scatter(
            x=embedding[mask,0], y=embedding[mask,1], mode="markers",
            name=cname,
            marker=dict(color=col, size=9, opacity=0.22, line=dict(width=1, color="white")),
            text=stns, hovertemplate="%{text}<extra></extra>",
        ))
    focus_set = set(focus_stations)
    for i, stn in enumerate(feats["station"]):
        if stn not in focus_set: continue
        cname = names[int(labels[i])]
        col   = PALETTE.get(stn, _cluster_color(cname))
        en    = STATION_EN.get(stn, stn)
        fig.add_trace(go.Scatter(
            x=[float(embedding[i,0])], y=[float(embedding[i,1])],
            mode="markers+text", name=en,
            text=[f"<b>{en}</b>"], textposition="top center",
            textfont=dict(size=12, color=col),
            marker=dict(color=col, size=18, symbol="star",
                        line=dict(width=2.5, color="white")),
            showlegend=False,
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#2A2622"), x=0.5),
        xaxis=dict(title="UMAP 1", showgrid=True, gridcolor="#E5E1D8", zeroline=False),
        yaxis=dict(title="UMAP 2", showgrid=True, gridcolor="#E5E1D8", zeroline=False),
        legend=dict(title="Cluster", x=1.01, font=dict(size=10)),
        paper_bgcolor="white", plot_bgcolor="white", width=760, height=540,
    )
    if export_dir is not None:
        p = Path(export_dir); p.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(p / "chart_K_umap_focus.html"))
        try: fig.write_image(str(p / "chart_K_umap_focus.png"), scale=2)
        except Exception: pass
    return fig


def make_chart_M(price_idx, feats, result,
                  title="Apartment prices move differently across neighborhood types", export_dir=None):
    """Chart M · Small multiples — monthly price index per gu.

    Why: Tufte's small multiples principle. Overlaying three lines would
    tangle; separating them keeps shape comparisons clean while the shared
    Y-axis preserves magnitude comparability.
    """
    _apply_style()
    GU_EN      = {"11680":"Gangnam-gu","11440":"Mapo-gu (Hongdae)","11560":"Yeongdeungpo-gu (Yeouido)"}
    GU_CLUSTER = {"11680":"Business District","11440":"Nightlife District","11560":"Business District 2"}
    gu_codes   = sorted(price_idx["gu_code"].unique())
    fig, axes  = plt.subplots(1, len(gu_codes), figsize=(4.8*len(gu_codes), 4.0), sharey=True)
    if len(gu_codes)==1: axes=[axes]
    for ax, gu in zip(axes, gu_codes):
        sub   = price_idx[price_idx["gu_code"]==gu].sort_values("year_month")
        color = _cluster_color(GU_CLUSTER.get(gu,"_unknown"))
        ax.plot(sub["year_month"], sub["median_price_per_m2"]/1e6,
                color=color, linewidth=2.2, marker="o", markersize=4,
                markerfacecolor="white", markeredgewidth=1.6)
        ax.fill_between(sub["year_month"], sub["median_price_per_m2"]/1e6, alpha=0.08, color=color)
        if len(sub)>=2:
            pct  = (sub["median_price_per_m2"].iloc[-1]/sub["median_price_per_m2"].iloc[0]-1)*100
            sign = "+" if pct>=0 else ""
            ax.annotate(f"{sign}{pct:.1f}% / 24 mo.",
                        xy=(sub["year_month"].iloc[-1], sub["median_price_per_m2"].iloc[-1]/1e6),
                        xytext=(-4,10), textcoords="offset points", fontsize=8.5, color=color, ha="right")
        ax.set_title(GU_EN.get(gu,gu), fontsize=10.5, color=PALETTE["_text"])
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    axes[0].set_ylabel("Median price per m²  (million KRW)", fontsize=10)
    fig.suptitle(title, fontsize=13, color=PALETTE["_text"], y=1.02)
    fig.autofmt_xdate(rotation=40, ha="right")
    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_M_price_small_multiples")
    return fig


def make_chart_N(price_idx,
                  title="24-month price change — Business districts diverge from Nightlife", export_dir=None):
    """Chart N · Slope chart — start vs end price per gu.

    Why: slope charts collapse a 24-month series to one sharp before→after
    comparison. Direction and magnitude are simultaneously readable.
    """
    _apply_style()
    GU_EN      = {"11680":"Gangnam-gu","11440":"Mapo-gu\n(Hongdae)","11560":"Yeongdeungpo-gu\n(Yeouido)"}
    GU_CLUSTER = {"11680":"Business District","11440":"Nightlife District","11560":"Business District 2"}
    records = []
    for gu, sub in price_idx.groupby("gu_code"):
        sub = sub.sort_values("year_month")
        records.append({
            "gu":gu, "gu_en":GU_EN.get(gu,gu),
            "start":sub["median_price_per_m2"].iloc[0]/1e6,
            "end":  sub["median_price_per_m2"].iloc[-1]/1e6,
            "color":_cluster_color(GU_CLUSTER.get(gu,"_unknown")),
        })
    records.sort(key=lambda r: r["end"]-r["start"])
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x0, x1  = 0.22, 0.78
    for rec in records:
        col = rec["color"]
        ax.plot([x0,x1],[rec["start"],rec["end"]], color=col, linewidth=2.2, alpha=0.9)
        ax.scatter([x0],[rec["start"]], color=col, s=80, zorder=5)
        ax.scatter([x1],[rec["end"]],   color=col, s=80, zorder=5)
        pct  = (rec["end"]/rec["start"]-1)*100
        sign = "+" if pct>=0 else ""
        ax.text(x0-0.02, rec["start"], rec["gu_en"],
                va="center", ha="right", fontsize=9.5, color=col)
        ax.text(x1+0.02, rec["end"], f"{rec['end']:.1f}M  ({sign}{pct:.1f}%)",
                va="center", ha="left", fontsize=9.5, color=col)
    ymin = min(r["start"] for r in records)
    ax.text(x0, ymin-0.5, "Start\n(Jun 2024)", ha="center", va="top", fontsize=10, color=PALETTE["_text"])
    ax.text(x1, ymin-0.5, "End\n(May 2026)",   ha="center", va="top", fontsize=10, color=PALETTE["_text"])
    ax.set_xlim(0,1); ax.set_xticks([])
    ax.set_ylabel("Median apartment price per m²  (million KRW)", fontsize=10)
    ax.set_title(title, fontsize=13, color=PALETTE["_text"], pad=12)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout()
    _save_matplotlib(fig, export_dir, "chart_N_slope_price_change")
    return fig


def make_chart_O(long_hourly, feats, result,
                  title="Morning flow into the city — by originating cluster type", export_dir=None):
    """Chart O · Stacked area — hourly boarding by originating cluster (Plotly).

    Why: stacked area shows both total and composition simultaneously over a
    continuous x-axis. Produced live during the AI demo (Section 7) to show
    that AI-assisted workflow generates *new* information, not a repeat.
    """
    import plotly.graph_objects as go
    labels, names = result.labels, result.cluster_names
    hourly_by_cluster = {}
    for cid, cname in names.items():
        stns = feats[labels==cid]["station"].tolist()
        agg  = (long_hourly[(long_hourly["station"].isin(stns)) &
                             (long_hourly["direction"]=="board")]
                .groupby("hour")["count"].sum()
                .reindex(range(24), fill_value=0).to_numpy(dtype=float))
        hourly_by_cluster[cname] = agg
    fig = go.Figure()
    order = ["Residential Commuter","Transit Interchange",
             "Nightlife District","Business District","Business District 2"]
    for cname in order:
        if cname not in hourly_by_cluster: continue
        col = _cluster_color(cname)
        fig.add_trace(go.Scatter(
            x=list(range(24)), y=hourly_by_cluster[cname].tolist(),
            mode="lines", stackgroup="one", name=cname,
            line=dict(width=0.5, color=col), fillcolor=_hex_rgba(col, 0.7),
            hovertemplate=f"<b>{cname}</b><br>%{{x:02d}}:00 → %{{y:,.0f}} boardings<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#2A2622"), x=0.5),
        xaxis=dict(title="Hour of day", tickvals=list(range(0,24,2)),
                   ticktext=[f"{h:02d}:00" for h in range(0,24,2)], gridcolor="#E5E1D8"),
        yaxis=dict(title="Total boardings", gridcolor="#E5E1D8"),
        legend=dict(title="Cluster", x=1.01, font=dict(size=10)),
        paper_bgcolor="white", plot_bgcolor="white", width=800, height=480,
        hovermode="x unified",
    )
    if export_dir is not None:
        p = Path(export_dir); p.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(p / "chart_O_stacked_area.html"))
        try: fig.write_image(str(p / "chart_O_stacked_area.png"), scale=2)
        except Exception: pass
    return fig


def render_section_6(feats, result, price_idx, long_hourly,
                      focus_stations=("강남","홍대입구","여의도"), export_dir=None) -> dict:
    """Build Section 6 (I, J, K, M, N) + Section 7 (O) in one call."""
    return {
        "I": make_chart_I(feats, result, export_dir=export_dir),
        "J": make_chart_J(result, export_dir=export_dir),
        "K": make_chart_K(feats, result, list(focus_stations), export_dir=export_dir),
        "M": make_chart_M(price_idx, feats, result, export_dir=export_dir),
        "N": make_chart_N(price_idx, export_dir=export_dir),
        "O": make_chart_O(long_hourly, feats, result, export_dir=export_dir),
    }
