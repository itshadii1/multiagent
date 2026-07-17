"""Presentation layer for the Streamlit app — CSS, theme tokens, small render
helpers, and the example-query list.

Kept out of `streamlit_app.py` so that file stays a thin caller of
`build_graph()`, exactly like the CLI: no styling logic leaks into the app
entrypoint, and no agent logic leaks in here. Nothing in this module imports
`research_agents` — it only knows how to paint.

Streamlit fixes its native theme at page load (from `.streamlit/config.toml`),
so a runtime light/dark switch can't go through that path. Instead the toggle
picks a token set here and we inject it as CSS custom properties, restyling the
app shell and the widgets that read those variables. The base config theme is
dark, so the first frame — painted before this CSS lands — already matches the
default and there's no light-mode flash.
"""

from __future__ import annotations

# --- theme tokens ------------------------------------------------------------
# One dict per mode. Every colour the CSS below uses comes from here, so adding
# a third theme later is a data change, not a CSS rewrite.

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0e1117",
        "surface": "#161a23",
        "surface_2": "#1c212c",
        "text": "#e6e9ef",
        "muted": "#9aa4b2",
        "border": "#262b36",
        "accent": "#22c55e",
        "accent_2": "#10b981",
        "shadow": "0 1px 3px rgba(0,0,0,.4)",
    },
    "light": {
        "bg": "#f6f7f9",
        "surface": "#ffffff",
        "surface_2": "#f0f2f6",
        "text": "#1a1d24",
        "muted": "#5a6472",
        "border": "#e3e7ee",
        "accent": "#16a34a",
        "accent_2": "#059669",
        "shadow": "0 1px 3px rgba(20,25,40,.08)",
    },
}

DEFAULT_THEME = "dark"

# Clickable starter queries. A recruiter won't invent a query; these lower the
# "what do I type" barrier to one click.
EXAMPLE_QUERIES: list[str] = [
    "Analyze the EV battery market in India",
    "How is generative AI changing the consulting industry?",
    "State of the Indian quick-commerce market in 2026",
    "Is green hydrogen viable for heavy transport?",
]


def theme_css(theme: str) -> str:
    """Return a `<style>` block that paints the whole app in `theme`.

    Targets Streamlit's stable `data-testid` hooks plus semantic tags, and
    drives everything off CSS variables so both modes share one stylesheet.
    """
    t = THEMES.get(theme, THEMES[DEFAULT_THEME])
    return f"""
<style>
:root {{
  --bg: {t['bg']};
  --surface: {t['surface']};
  --surface-2: {t['surface_2']};
  --text: {t['text']};
  --muted: {t['muted']};
  --border: {t['border']};
  --accent: {t['accent']};
  --accent-2: {t['accent_2']};
  --shadow: {t['shadow']};
}}

/* App shell ------------------------------------------------------------- */
.stApp, [data-testid="stAppViewContainer"] {{
  background: var(--bg);
  color: var(--text);
}}
[data-testid="stHeader"] {{ background: transparent; }}
/* Streamlit paints the sidebar fill on the inner content wrapper, so target
   both the section and its child and win with !important. */
section[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
  background: var(--surface) !important;
  border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color: var(--text); }}
[data-testid="stSidebar"] .section-label {{ color: var(--muted); }}

/* Hide the default Streamlit chrome we replace with our own header. */
#MainMenu, footer {{ visibility: hidden; }}

.block-container {{ padding-top: 2.2rem; max-width: 860px; }}

h1, h2, h3, h4, p, span, label, li {{ color: var(--text); }}

/* Hero ------------------------------------------------------------------ */
.hero-title {{
  font-size: 2.9rem;
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.02em;
  margin: 0 0 .35rem 0;
  color: var(--text);
}}
.hero-sub {{
  color: var(--muted);
  font-size: 1.05rem;
  margin: 0 0 .25rem 0;
  max-width: 640px;
}}

/* Pipeline strip -------------------------------------------------------- */
.pipeline {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .4rem;
  margin: 1.4rem 0 1.8rem 0;
}}
.pipe-node {{
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .38rem .7rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  font-size: .82rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}}
.pipe-node .dot {{
  width: .5rem; height: .5rem; border-radius: 50%;
  background: var(--accent);
}}
.pipe-arrow {{ color: var(--muted); font-size: .9rem; }}
.pipe-loop {{
  color: var(--accent);
  font-size: .78rem;
  font-weight: 600;
  margin-left: .1rem;
}}

/* Section labels -------------------------------------------------------- */
.section-label {{
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: .74rem;
  font-weight: 700;
  color: var(--muted);
  margin: 0 0 .5rem 0;
}}

/* Inputs & buttons ------------------------------------------------------ */
[data-testid="stTextInput"] input {{
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: .7rem .9rem !important;
}}
[data-testid="stTextInput"] input:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent) !important;
}}

/* Primary run button. */
[data-testid="stButton"] button[kind="primary"] {{
  background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  padding: .55rem 1.4rem !important;
}}
[data-testid="stButton"] button[kind="primary"]:hover {{ filter: brightness(1.08); }}
[data-testid="stButton"] button[kind="primary"]:disabled {{
  opacity: .5 !important; filter: none !important;
}}

/* Secondary / example-chip buttons. */
[data-testid="stButton"] button[kind="secondary"] {{
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 999px !important;
  font-size: .82rem !important;
  font-weight: 500 !important;
  padding: .32rem .8rem !important;
}}
[data-testid="stButton"] button[kind="secondary"]:hover {{
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}}

/* Metric cards ---------------------------------------------------------- */
[data-testid="stMetric"] {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: .9rem 1rem;
  box-shadow: var(--shadow);
}}
[data-testid="stMetricValue"] {{ color: var(--text); font-weight: 800; }}
[data-testid="stMetricLabel"] {{ color: var(--muted); }}

/* Report surface -------------------------------------------------------- */
.report-frame {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: .2rem 1.6rem 1rem 1.6rem;
  box-shadow: var(--shadow);
}}

/* Status / expander surfaces pick up the theme too. */
[data-testid="stExpander"], [data-testid="stStatus"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
}}
</style>
"""


# --- render helpers ----------------------------------------------------------
# These return HTML strings; the app passes them to `st.markdown(..., unsafe_
# allow_html=True)`. Kept as pure string builders so they're trivially testable
# and carry no Streamlit dependency.

def hero_html(title: str, subtitle: str) -> str:
    return (
        f'<h1 class="hero-title">{title}</h1>'
        f'<p class="hero-sub">{subtitle}</p>'
    )


_PIPELINE_STAGES = [
    ("Planner", "splits into sub-questions"),
    ("Researchers", "search the web in parallel"),
    ("Writer", "drafts a cited report"),
    ("Critic", "reviews & can send it back"),
    ("Evaluator", "scores the result"),
]


def pipeline_html() -> str:
    """A static strip of the four-agent flow, shown before a run so the
    architecture reads even on an idle page."""
    parts: list[str] = ['<div class="pipeline">']
    for i, (name, _desc) in enumerate(_PIPELINE_STAGES):
        parts.append(f'<span class="pipe-node"><span class="dot"></span>{name}</span>')
        if i < len(_PIPELINE_STAGES) - 1:
            # The critic can loop back to the writer — mark that edge.
            if name == "Critic":
                parts.append('<span class="pipe-loop">⟲ revise</span>')
            parts.append('<span class="pipe-arrow">→</span>')
    parts.append("</div>")
    return "".join(parts)
