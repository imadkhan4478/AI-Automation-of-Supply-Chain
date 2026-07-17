"""
Design tokens — the single source of truth for the app's visual language.

Every color, font, and status meaning is defined ONCE here. Components and
pages import from this file, so a brand change happens in one place.

Palette philosophy:
  - NAVY  = structure (headers, text, chrome)
  - GOLD  = brand accent, used sparingly for emphasis
  - R/A/G = status ONLY. Red/amber/green never appear as decoration,
            only to communicate risk / watch / healthy. This discipline
            is what separates an enterprise look from a prototype.
"""

# --- Brand ---
NAVY        = "#1F2D4E"   # primary structure
NAVY_DEEP   = "#16223C"   # sidebar / darker surfaces
GOLD        = "#BF9000"   # brand accent
GOLD_SOFT   = "#E7D9A8"   # subtle accent fills

# --- Neutrals ---
INK         = "#1F2D4E"   # main text (same as navy for cohesion)
MUTED       = "#5A6478"   # secondary text
LINE        = "#E4E8F0"   # borders / dividers
SURFACE     = "#FFFFFF"   # cards
CANVAS      = "#F4F6FA"   # page background
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
CHART_SEQUENCE = [NAVY, GOLD, "#4A6FA5", "#8C6D1F", "#7089B0", "#C7A93E"]

# --- Type ---
FONT_STACK = "'Segoe UI', 'Inter', system-ui, -apple-system, sans-serif"

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
