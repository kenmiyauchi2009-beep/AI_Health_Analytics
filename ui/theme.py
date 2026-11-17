"""Central styling. Colours, type and radii live in .streamlit/config.toml; this file only adds what the
theme can't express. Selectors target Streamlit's documented hooks — ``st-key-<key>`` classes on keyed
containers and ``data-testid`` attributes — never generated class names.
"""

from __future__ import annotations

import streamlit as st

PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
TEAL = "#0D9488"
TEXT = "#0F172A"
TEXT_MUTED = "#64748B"
BORDER = "#E2E8F0"
SURFACE = "#FFFFFF"
SUCCESS = "#16A34A"
WARNING = "#D97706"
ERROR = "#DC2626"

# Streamlit's named colours for badges and markdown. "violet" is themed to teal in config.toml.
BADGE_COLOR_TEAL = "violet"

_CSS = f"""
<style>
/* Readable line length on wide screens; Streamlit stacks columns on narrow ones. */
[data-testid="stMainBlockContainer"] {{
    max-width: 1180px;
    padding-top: 2.25rem;
    padding-bottom: 4rem;
}}

/* Cards: any container keyed "card-..." is a white surface. Raised cards get a slightly deeper shadow. */
[class*="st-key-card-"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}}
[class*="st-key-card-raised-"] {{
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 6px 16px rgba(15, 23, 42, 0.04);
}}

/* Provenance lanes on analysis results: the card's left edge says where a result came from. */
[class*="st-key-card-lane-model-"] {{ border-left: 3px solid {PRIMARY}; }}
[class*="st-key-card-lane-subgroup-"] {{ border-left: 3px solid {TEAL}; }}
[class*="st-key-card-lane-ai-"] {{ border-left: 3px solid {TEXT_MUTED}; }}

/* Empty states sit centred inside their card. */
[class*="st-key-card-empty-"] {{
    text-align: center;
    padding: 2rem 1.5rem;
}}

[data-testid="stBaseButton-primary"]:hover {{
    background-color: {PRIMARY_HOVER};
    border-color: {PRIMARY_HOVER};
}}

/* Text-style (tertiary) buttons read as links. */
[data-testid="stBaseButton-tertiary"] {{ color: {PRIMARY}; }}
[data-testid="stBaseButton-tertiary"]:hover {{ color: {PRIMARY_HOVER}; }}

[data-testid="stSidebarUserContent"] {{ padding-top: 1rem; }}

@media (prefers-reduced-motion: reduce) {{
    * {{ transition: none !important; animation: none !important; }}
}}
</style>
"""


def apply_theme() -> None:
    """Inject the shared stylesheet. Call once per run, from app.py."""
    st.html(_CSS)
