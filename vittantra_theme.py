"""
Vittantra design system — "Night private bank": deep green-black background,
brass accents, serif headings and monospaced numbers.

One place for colours and chart styling, so every page looks the same.
Import the constants in pages; `apply_plotly_theme()` makes the template the
default for every Plotly chart.
"""

from __future__ import annotations

# Brand (dark)
GREEN = "#07100D"        # sidebar
FOREST = "#5FA88A"       # main data colour (bars, primary series) — light enough on dark
BRASS = "#D4B062"        # accent: highlights, the series that matters most
SAGE = "#6E8C7E"         # secondary series, benchmarks
IVORY = "#0B1612"        # page background (name kept for compatibility)
PAPER = "#10201A"        # cards / panels
LINE = "#1E2E28"         # borders and gridlines
INK = "#E9E4D6"          # text
MUTED = "#8FA39A"        # secondary text

# Meaning (separate from the brand accent)
POSITIVE = "#5FD3A1"
NEGATIVE = "#F07C7C"
WARNING = "#E0B64D"

# Categorical order for multi-series charts (distinct but in the same family)
CATEGORICAL = [FOREST, BRASS, "#7FB3D5", "#C39BD3", SAGE, "#E59866", "#76D7C4", "#F1948A", "#AAB7B8", "#F7DC6F"]

# Diverging scale: brick → ivory → green
DIVERGING = [[0.0, "#C0504D"], [0.5, "#14251F"], [1.0, "#4FA37F"]]

FONT_BODY = "IBM Plex Sans, system-ui, sans-serif"
FONT_DATA = "IBM Plex Mono, ui-monospace, monospace"
FONT_HEADING = "Source Serif 4, Georgia, serif"


def band(color: str, alpha: float) -> str:
    """Hex colour → rgba() string with transparency (for fan charts and fills)."""
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def apply_plotly_theme() -> None:
    import plotly.graph_objects as go
    import plotly.io as pio

    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT_BODY, color=INK, size=13),
        title=dict(font=dict(family=FONT_HEADING, size=17, color=INK), x=0, xanchor="left"),
        colorway=CATEGORICAL,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=LINE, linecolor=LINE, zerolinecolor=LINE, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=LINE, linecolor=LINE, zerolinecolor="#2F453C", tickfont=dict(color=MUTED)),
        legend=dict(font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=PAPER, bordercolor=LINE, font=dict(family=FONT_BODY, color=INK)),
        colorscale=dict(diverging=DIVERGING, sequential=[[0, "#14251F"], [1, BRASS]]),
    )
    pio.templates["vittantra"] = template
    pio.templates.default = "plotly_dark+vittantra"
