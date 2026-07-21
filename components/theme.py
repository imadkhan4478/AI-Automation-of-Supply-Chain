"""
Design tokens — the single source of truth for the app's visual language.

Every color, font, and status meaning is defined ONCE here. Components and
pages import from this file, so a brand change happens in one place.

Palette philosophy (restrained SaaS, not a rainbow):
  - NAVY   = ink (body text, headers) — dark/high-contrast for readability.
  - CANVAS/SURFACE = neutral near-white (light) / near-black (dark). Color is
    not page decoration — a confident, minimal product doesn't need a
    colored background to look designed.
  - BRAND/VIOLET = the ONE signature gradient, used with intent (active
    nav, primary chart series, the brand mark) — not spread across every
    page in a different hue.
  - MODULES  = each page still gets a distinguishing accent color, but it
    shows up small (an icon badge, an illustration) — never as a full-page
    wash. Color as data/identity, not decoration.
  - GOLD   = warm brand accent, used sparingly for emphasis.
  - R/A/G  = status ONLY. Red/amber/green never appear as decoration,
             only to communicate risk / watch / healthy.

Dark mode: every token below is duplicated in _LIGHT/_DARK and exposed as a
plain module attribute (T.NAVY, T.SURFACE, ...) for ergonomic call sites
elsewhere (`from components import theme as T; T.NAVY`). Streamlit only
imports a module once per server process — reruns don't re-execute this
file — so switching modes can't rely on re-import. Instead `set_mode()`
reassigns this module's globals in place; every other file reads T.XXX as a
plain attribute lookup *at call time* (inside function bodies that re-run
every script rerun), so calling set_mode() once at the top of app.py before
anything renders is enough for the whole app — including already-imported
pages/components — to pick up the new palette that render.
"""

# --- Brand accents that don't change between modes ---
BRAND        = "#4F46E5"   # indigo-600 — primary accent, used with intent
BRAND_DEEP   = "#3730A3"   # indigo-800 — gradient partner / hover
BRAND_LIGHT  = "#818CF8"   # indigo-400 — light tint, chips
VIOLET       = "#8B5CF6"   # violet-500 — secondary gradient stop
GOLD         = "#BF9000"   # warm brand accent
GRADIENT_BRAND = f"linear-gradient(135deg, {BRAND} 0%, {VIOLET} 100%)"

# --- Type ---
# Manrope (Google Font, loaded in ui.inject_styles) for headlines/numbers —
# the single highest-impact change for reading as "designed" rather than
# "default app font." System sans stays as the body-text/UI fallback.
DISPLAY_FONT_NAME = "Manrope"
DISPLAY_FONT_URL = "https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap"
DISPLAY_FONT_STACK = "'Manrope', 'Segoe UI', system-ui, -apple-system, sans-serif"
FONT_STACK = "'Segoe UI', system-ui, -apple-system, sans-serif"

# --- Chart sequence (used for categorical charts, brand-led) ---
CHART_SEQUENCE = [BRAND, GOLD, VIOLET, "#4A6FA5", "#8C6D1F", "#7089B0"]

# --- Per-module identity: accent stays fixed, "soft" tint flips per mode ---
_MODULE_ACCENTS = {
    "dashboard": BRAND,
    "purchases": "#F59E0B",
    "inventory": "#10B981",
    "imports":   "#0EA5E9",
    "logistics": "#FB7185",
    "reports":   "#06B6D4",
    "assistant": "#8B5CF6",
}
_MODULE_SOFT_LIGHT = {
    "dashboard": "#EEECFC", "purchases": "#FEF3E2", "inventory": "#E6F7F1",
    "imports": "#E5F4FC", "logistics": "#FDEBEE", "reports": "#E3F7FA", "assistant": "#F1EDFC",
}
_MODULE_SOFT_DARK = {
    "dashboard": "#2A2550", "purchases": "#3D2E12", "inventory": "#123328",
    "imports": "#0F2C3D", "logistics": "#3D1F26", "reports": "#0F323A", "assistant": "#2C2050",
}

MODULE_ICONS = {
    # gauge / speedometer
    "dashboard": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    # shopping cart
    "purchases": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/>'
                 '<path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    # package / box
    "inventory": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73Z"/>'
                 '<path d="M12 22V12"/><path d="m3.3 7 8.7 5 8.7-5"/>',
    # plane
    "imports":   '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    # truck
    "logistics": '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/>'
                 '<path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/>'
                 '<circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
    # bar chart
    "reports":   '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    # chat bubble
    "assistant": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
}

# --- Status roles: a label maps to a ROLE name, not a baked-in color tuple,
# so status_colors() always reflects the CURRENT mode's R/A/G colors rather
# than whatever was active when this dict was first built at import time. ---
# NOTE: the "arrived" = healthy, "in process/awaiting/under" = watch,
# "cancelled" = risk grouping below for import_details.current_status is a
# placeholder business rule (same spirit as the delay/reorder rules in
# backend/data_access.py) until the business confirms real terminal states.
_STATUS_ROLES = {
    "delayed": "risk", "pending clearance": "risk", "below reorder": "risk",
    "out of stock": "risk", "critical": "risk", "order cancelled": "risk",
    "incomplete": "risk",
    "pending": "watch", "in transit": "watch", "watch": "watch",
    "under production": "watch", "ready awaiting sailing": "watch",
    "under custom clearance": "watch", "costing in process": "watch",
    "lc in process": "watch", "t/t in process": "watch", "under de-stuffing": "watch",
    "sailing": "watch", "at qfl": "watch", "at port": "watch",
    "pending packing": "watch", "in progress": "watch", "near complete": "watch",
    "completed": "healthy", "cleared": "healthy", "ok": "healthy", "delivered": "healthy",
    "healthy": "healthy", "arrived at works": "healthy", "arrived at qfl": "healthy",
    "complete": "healthy",
}

# --- The two palettes ---
_LIGHT = dict(
    NAVY="#1F2D4E", NAVY_DEEP="#16223C", GOLD_SOFT="#E7D9A8", BRAND_SOFT="#EEECFC",
    INK="#1F2D4E", MUTED="#5A6478", LINE="#E6E8EF",
    SURFACE="#FFFFFF", CANVAS="#F7F8FB", CANVAS_ALT="#F0F1F5", SIDEBAR_BG="#FFFFFF",
    RISK="#C0392B", RISK_BG="#FDECEC", WATCH="#B9770E", WATCH_BG="#FEF6E7",
    HEALTHY="#1E8449", HEALTHY_BG="#E9F7EF", INFO="#2E5AAC", INFO_BG="#EAF2FB",
)
_DARK = dict(
    NAVY="#F1F3F9", NAVY_DEEP="#0B0E14", GOLD_SOFT="#8A6D2A", BRAND_SOFT="#241F3D",
    INK="#F1F3F9", MUTED="#9AA3B8", LINE="#2A2E3D",
    SURFACE="#171A24", CANVAS="#0E1017", CANVAS_ALT="#1D202C", SIDEBAR_BG="#12141C",
    RISK="#F27E71", RISK_BG="#3A1E1E", WATCH="#E8AE4D", WATCH_BG="#3A2E14",
    HEALTHY="#4ADE80", HEALTHY_BG="#173A26", INFO="#7CA6F0", INFO_BG="#1A2C4A",
)

DARK_MODE = False


def set_mode(dark: bool):
    """Switch the active palette. Call once at the very top of app.py,
    before inject_styles()/any page renders, so every T.XXX attribute read
    for the rest of this script run resolves to the chosen mode.
    """
    global DARK_MODE
    DARK_MODE = bool(dark)
    globals().update(_DARK if dark else _LIGHT)


def module_colors(module):
    """(accent, soft-background) for a module badge, mode-aware."""
    accent = _MODULE_ACCENTS.get(module, BRAND)
    soft = (_MODULE_SOFT_DARK if DARK_MODE else _MODULE_SOFT_LIGHT).get(
        module, _MODULE_SOFT_DARK["dashboard"] if DARK_MODE else _MODULE_SOFT_LIGHT["dashboard"])
    return accent, soft


def status_colors(label):
    """Return (fg, bg) for a status label, resolved against the CURRENT
    mode's colors — falls back to info blue."""
    role = _STATUS_ROLES.get(str(label).strip().lower())
    return {
        "risk": (RISK, RISK_BG), "watch": (WATCH, WATCH_BG), "healthy": (HEALTHY, HEALTHY_BG),
    }.get(role, (INFO, INFO_BG))


set_mode(False)  # initialize module attributes to the light palette by default
