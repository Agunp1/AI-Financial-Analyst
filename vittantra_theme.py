"""
Vittantra design system — "Private bank" (deep green, brass, serif headings).

One place for colours and chart styling, so every page looks the same.
Import the constants in pages; `apply_plotly_theme()` makes the template the
default for every Plotly chart.
"""

from __future__ import annotations

# Brand
GREEN = "#123D30"        # sidebar, hero, primary buttons
FOREST = "#1F5C47"       # main data colour (bars, primary series)
BRASS = "#A9843A"        # accent: highlights, the series that matters most
SAGE = "#9FB5AA"         # secondary series, benchmarks
IVORY = "#FBFAF7"        # page background
PAPER = "#FFFFFF"        # cards
LINE = "#E4E1D8"         # borders and gridlines
INK = "#1B2A24"          # text
MUTED = "#66736C"        # secondary text

# Meaning (separate from the brand accent)
POSITIVE = "#1F6E4E"
NEGATIVE = "#9C2F2F"
WARNING = "#B07A12"

# Categorical order for multi-series charts (distinct but in the same family)
CATEGORICAL = [FOREST, BRASS, SAGE, "#3F7F9C", "#7A5C8E", "#C9A961", "#5E8B73", "#B5654A", "#2F4858", "#8C9A90"]

# Diverging scale: brick → ivory → green
DIVERGING = [[0.0, NEGATIVE], [0.5, "#F7F4EC"], [1.0, FOREST]]

FONT_BODY = "IBM Plex Sans, system-ui, sans-serif"
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
        yaxis=dict(gridcolor=LINE, linecolor=LINE, zerolinecolor="#CFCABD", tickfont=dict(color=MUTED)),
        legend=dict(font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=PAPER, bordercolor=LINE, font=dict(family=FONT_BODY, color=INK)),
        colorscale=dict(diverging=DIVERGING, sequential=[[0, "#F7F4EC"], [1, FOREST]]),
    )
    pio.templates["vittantra"] = template
    pio.templates.default = "plotly_white+vittantra"
