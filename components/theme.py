"""
Design tokens — the single source of truth for the app's visual language.

Every color, font, and status meaning is defined ONCE here. Components and
pages import from this file, so a brand change happens in one place.

Palette philosophy:
  - NAVY   = ink (body text, headers) — kept dark/high-contrast for readability.
  - BRAND/VIOLET = the vivid gradient accent (cards, sidebar, charts, active
    states) that replaces the old flat-white/navy-only look.
  - GOLD   = warm brand accent, used sparingly for emphasis (unchanged role).
  - R/A/G  = status ONLY. Red/amber/green never appear as decoration,
             only to communicate risk / watch / healthy. This discipline
             is what separates an enterprise look from a prototype.
"""

# --- Brand: ink + structure (unchanged — stays high-contrast for text) ---
NAVY        = "#1F2D4E"   # primary structure / body text
NAVY_DEEP   = "#16223C"   # darker surfaces
GOLD        = "#BF9000"   # warm brand accent
GOLD_SOFT   = "#E7D9A8"   # subtle accent fills

# --- Brand: vivid gradient accent (new) ---
BRAND        = "#4F46E5"   # indigo-600 — primary vivid accent
BRAND_DEEP   = "#3730A3"   # indigo-800 — gradient partner / hover / sidebar
BRAND_LIGHT  = "#818CF8"   # indigo-400 — light tint, chips
BRAND_SOFT   = "#EEECFC"   # indigo-50  — soft fills, chip backgrounds
VIOLET       = "#8B5CF6"   # violet-500 — secondary gradient stop

GRADIENT_BRAND   = f"linear-gradient(135deg, {BRAND} 0%, {VIOLET} 100%)"
GRADIENT_SIDEBAR = f"linear-gradient(180deg, {NAVY_DEEP} 0%, {BRAND_DEEP} 100%)"
GRADIENT_CANVAS  = "linear-gradient(160deg, #F7F6FF 0%, #F2F1FB 45%, #FBF6EA 100%)"

# --- Neutrals ---
INK         = "#1F2D4E"   # main text (same as navy for cohesion)
MUTED       = "#5A6478"   # secondary text
LINE        = "#E4E8F0"   # borders / dividers
SURFACE     = "#FFFFFF"   # cards
CANVAS      = "#F4F6FA"   # page background (flat fallback; GRADIENT_CANVAS used where supported)
CANVAS_ALT  = "#EEF1F7"   # zebra / subtle fills

# --- Semantic status (R/A/G) ---
RISK        = "#C0392B"   # red   — delayed, at risk, critical
RISK_BG     = "#FDECEC"
WATCH       = "#B9770E"   # amber — pending, watch
WATCH_BG    = "#FEF6E7"
HEALTHY     = "#1E8449"   # green — on time, ok, healthy
HEALTHY_BG  = "#E9F7EF"
INFO        = "#2E5AAC"   # blue  — informational
INFO_BG     = "#EAF2FB"

# --- Chart sequence (used for categorical charts, brand-led) ---
CHART_SEQUENCE = [BRAND, GOLD, VIOLET, "#4A6FA5", "#8C6D1F", "#7089B0"]

# --- Type ---
FONT_STACK = "'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif"

# --- Per-module identity ---
# Each page gets its own gradient + a low-opacity watermark icon on its
# header banner, so Purchases/Inventory/Imports/Logistics/Reports/Assistant
# each read as visually distinct at a glance, not just a color swap of the
# same page. Icon paths are simplified Lucide-style line icons (public
# domain shapes), inlined as raw SVG so there's no external icon-font
# dependency.
MODULES = {
    "dashboard": {"gradient": GRADIENT_BRAND, "solid": BRAND},
    "purchases": {"gradient": "linear-gradient(135deg, #F59E0B 0%, #FB923C 100%)", "solid": "#F59E0B"},
    "inventory": {"gradient": "linear-gradient(135deg, #10B981 0%, #14B8A6 100%)", "solid": "#10B981"},
    "imports":   {"gradient": "linear-gradient(135deg, #0EA5E9 0%, #3B82F6 100%)", "solid": "#0EA5E9"},
    "logistics": {"gradient": "linear-gradient(135deg, #FB7185 0%, #F472B6 100%)", "solid": "#FB7185"},
    "reports":   {"gradient": "linear-gradient(135deg, #06B6D4 0%, #0EA5E9 100%)", "solid": "#06B6D4"},
    "assistant": {"gradient": "linear-gradient(135deg, #8B5CF6 0%, #D946EF 100%)", "solid": "#8B5CF6"},
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

# --- Status lookup helper ---
# NOTE: the "arrived" = healthy, "in process/awaiting/under" = watch,
# "cancelled" = risk grouping below for import_details.current_status is a
# placeholder business rule (same spirit as the delay/reorder rules in
# backend/data_access.py) until the business confirms real terminal states.
STATUS_MAP = {
    # purchases / imports / general
    "delayed":                 (RISK, RISK_BG),
    "pending clearance":       (RISK, RISK_BG),
    "below reorder":           (RISK, RISK_BG),
    "critical":                (RISK, RISK_BG),
    "order cancelled":         (RISK, RISK_BG),
    "pending":                 (WATCH, WATCH_BG),
    "in transit":              (WATCH, WATCH_BG),
    "watch":                   (WATCH, WATCH_BG),
    "under production":        (WATCH, WATCH_BG),
    "ready awaiting sailing":  (WATCH, WATCH_BG),
    "under custom clearance":  (WATCH, WATCH_BG),
    "costing in process":      (WATCH, WATCH_BG),
    "lc in process":           (WATCH, WATCH_BG),
    "t/t in process":          (WATCH, WATCH_BG),
    "under de-stuffing":       (WATCH, WATCH_BG),
    "completed":               (HEALTHY, HEALTHY_BG),
    "cleared":                 (HEALTHY, HEALTHY_BG),
    "ok":                      (HEALTHY, HEALTHY_BG),
    "delivered":               (HEALTHY, HEALTHY_BG),
    "healthy":                 (HEALTHY, HEALTHY_BG),
    "arrived at works":        (HEALTHY, HEALTHY_BG),
    "arrived at qfl":          (HEALTHY, HEALTHY_BG),
}


def status_colors(label):
    """Return (fg, bg) for a status label; falls back to info blue."""
    return STATUS_MAP.get(str(label).strip().lower(), (INFO, INFO_BG))
