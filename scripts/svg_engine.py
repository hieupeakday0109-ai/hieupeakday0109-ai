import html
import json
import math
import os
import textwrap

THEMES = {
    "dark": {
        "canvas": "#070709",
        "surface": "#0c0c12",
        "panel": "#13141c",
        "panel_alt": "#181924",
        "border": "#232430",
        "border_hi": "#383a4d",
        "ink": "#f8fafc",
        "ink2": "#a1a1aa",
        "muted": "#71717a",
        "grid": "#ffffff",
        "grid_op": "0.035",
        "cyan": "#38bdf8",
        "emerald": "#10b981",
        "violet": "#8b5cf6",
        "rose": "#f43f5e",
        "amber": "#f59e0b",
        "pill_bg": "#11121a",
        "pill_label": "#09090d",
        "glow_op": "0.24",
    },
    "light": {
        "canvas": "#f8fafc",
        "surface": "#ffffff",
        "panel": "#f1f5f9",
        "panel_alt": "#e2e8f0",
        "border": "#cbd5e1",
        "border_hi": "#94a3b8",
        "ink": "#09090b",
        "ink2": "#334155",
        "muted": "#64748b",
        "grid": "#0f172a",
        "grid_op": "0.045",
        "cyan": "#0284c7",
        "emerald": "#059669",
        "violet": "#7c3aed",
        "rose": "#e11d48",
        "amber": "#d97706",
        "pill_bg": "#ffffff",
        "pill_label": "#f1f5f9",
        "glow_op": "0.14",
    },
}

FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
FONT_MONO = "'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _rotate_point(pt, ax, ay, az):
    x, y, z = pt
    # Rotate around X
    cy, sy = math.cos(ax), math.sin(ax)
    y, z = y * cy - z * sy, y * sy + z * cy
    # Rotate around Y
    cx, sx = math.cos(ay), math.sin(ay)
    x, z = x * cx + z * sx, -x * sx + z * cx
    # Rotate around Z
    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz
    return x, y, z


def _icosahedron_wireframe_frames(cx: float, cy: float, radius: float, steps: int = 24):
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    raw_verts = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]
    verts = []
    for vx, vy, vz in raw_verts:
        norm = math.sqrt(vx * vx + vy * vy + vz * vz)
        verts.append((vx / norm, vy / norm, vz / norm))

    edges = []
    for i in range(len(verts)):
        for j in range(i + 1, len(verts)):
            dx = verts[i][0] - verts[j][0]
            dy = verts[i][1] - verts[j][1]
            dz = verts[i][2] - verts[j][2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < 1.2:
                edges.append((i, j))

    paths = []
    for s in range(steps + 1):
        t = (s / steps) * 2.0 * math.pi
        ax = 0.45 + 0.25 * math.sin(t)
        ay = t
        az = 0.2 * math.cos(t)
        proj = []
        for v in verts:
            rx, ry, rz = _rotate_point(v, ax, ay, az)
            persp = 3.2 / (3.2 - rz * 0.75)
            px = cx + rx * radius * persp
            py = cy + ry * radius * persp
            proj.append((px, py))
        cmds = []
        for i, j in edges:
            x1, y1 = proj[i]
            x2, y2 = proj[j]
            cmds.append(f"M{x1:.1f},{y1:.1f}L{x2:.1f},{y2:.1f}")
        paths.append("".join(cmds))
    return paths


def _octa_gyro_frames(cx: float, cy: float, radius: float, steps: int = 24):
    verts = [
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1),
    ]
    edges = [
        (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 4), (4, 3), (3, 5), (5, 2),
    ]
    paths = []
    for s in range(steps + 1):
        t = (s / steps) * 2.0 * math.pi
        ax = 0.55
        ay = -t
        az = 0.35 * math.sin(t)
        proj = []
        for v in verts:
            rx, ry, rz = _rotate_point(v, ax, ay, az)
            persp = 3.0 / (3.0 - rz * 0.7)
            proj.append((cx + rx * radius * persp, cy + ry * radius * persp))
        paths.append("".join(f"M{proj[i][0]:.1f},{proj[i][1]:.1f}L{proj[j][0]:.1f},{proj[j][1]:.1f}" for i, j in edges))
    return paths


def build_banner(data: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    u = data["user"]
    c = data["contributions"]
    ico_frames = _icosahedron_wireframe_frames(136, 146, 56, steps=24)
    oct_frames = _octa_gyro_frames(864, 146, 52, steps=24)
    ico_vals = ";".join(ico_frames)
    oct_vals = ";".join(oct_frames)
    synced = esc(data.get("synced_at", "2026"))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 276" width="100%" height="276" role="img" aria-label="HieuPeak Obsidian Masthead">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t['canvas']}" />
      <stop offset="50%" stop-color="{t['surface']}" />
      <stop offset="100%" stop-color="{t['canvas']}" />
    </linearGradient>
    <radialGradient id="coreGlow" cx="50%" cy="48%" r="48%">
      <stop offset="0%" stop-color="{t['cyan']}" stop-opacity="{t['glow_op']}" />
      <stop offset="55%" stop-color="{t['violet']}" stop-opacity="0.10" />
      <stop offset="100%" stop-color="{t['canvas']}" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['ink2']}" />
      <stop offset="35%" stop-color="{t['ink']}" />
      <stop offset="50%" stop-color="{t['cyan']}" />
      <stop offset="65%" stop-color="{t['ink']}" />
      <stop offset="100%" stop-color="{t['ink2']}" />
    </linearGradient>
    <linearGradient id="accentBar" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['cyan']}" stop-opacity="0" />
      <stop offset="30%" stop-color="{t['cyan']}" />
      <stop offset="50%" stop-color="{t['ink']}" />
      <stop offset="70%" stop-color="{t['violet']}" />
      <stop offset="100%" stop-color="{t['violet']}" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="scanGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['cyan']}" stop-opacity="0" />
      <stop offset="50%" stop-color="{t['cyan']}" stop-opacity="0.12" />
      <stop offset="100%" stop-color="{t['cyan']}" stop-opacity="0" />
    </linearGradient>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M 24 0 L 0 0 0 24" fill="none" stroke="{t['grid']}" stroke-width="0.6" stroke-opacity="{t['grid_op']}" />
      <circle cx="24" cy="24" r="0.8" fill="{t['grid']}" fill-opacity="{t['grid_op']}" />
    </pattern>
    <clipPath id="cardClip">
      <rect x="2" y="2" width="996" height="272" rx="14" />
    </clipPath>
  </defs>

  <style>
    .mono {{ font-family: {FONT_MONO}; }}
    .sans {{ font-family: {FONT_SANS}; }}
    @keyframes pulseDot {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.35; transform: scale(0.82); }}
    }}
    @keyframes scanSweep {{
      0% {{ transform: translateX(-260px); }}
      100% {{ transform: translateX(1120px); }}
    }}
    @keyframes fadeFloat {{
      0%, 100% {{ opacity: 0.25; }}
      50% {{ opacity: 0.52; }}
    }}
    .beacon {{ transform-origin: 36px 34px; animation: pulseDot 2.2s ease-in-out infinite; }}
    .scan {{ animation: scanSweep 6.5s cubic-bezier(0.22, 1, 0.36, 1) infinite; }}
    .glow-pulse {{ animation: fadeFloat 5.5s ease-in-out infinite; }}
  </style>

  <g clip-path="url(#cardClip)">
    <rect x="2" y="2" width="996" height="272" rx="14" fill="url(#bg)" />
    <rect x="2" y="2" width="996" height="272" rx="14" fill="url(#coreGlow)" class="glow-pulse" />
    <rect x="2" y="2" width="996" height="272" rx="14" fill="url(#grid)" />
    <rect x="0" y="2" width="220" height="272" fill="url(#scanGrad)" class="scan" />

    <!-- Left 3D Projected Wireframe Icosahedron + Orbital Rings -->
    <g opacity="0.85">
      <circle cx="136" cy="146" r="76" fill="none" stroke="{t['border_hi']}" stroke-width="0.9" stroke-dasharray="4 6">
        <animateTransform attributeName="transform" type="rotate" from="0 136 146" to="360 136 146" dur="22s" repeatCount="indefinite" />
      </circle>
      <ellipse cx="136" cy="146" rx="84" ry="28" fill="none" stroke="{t['cyan']}" stroke-width="0.8" stroke-opacity="0.35" transform="rotate(-18 136 146)" />
      <path d="{ico_frames[0]}" fill="none" stroke="{t['cyan']}" stroke-width="1.25" stroke-opacity="0.55" stroke-linejoin="round">
        <animate attributeName="d" values="{ico_vals}" dur="12s" repeatCount="indefinite" />
      </path>
      <circle cx="136" cy="146" r="3" fill="{t['cyan']}" opacity="0.85" />
    </g>

    <!-- Right 3D Projected Octahedron Gyroscope + Orbital Rings -->
    <g opacity="0.85">
      <circle cx="864" cy="146" r="74" fill="none" stroke="{t['border_hi']}" stroke-width="0.9" stroke-dasharray="3 5">
        <animateTransform attributeName="transform" type="rotate" from="360 864 146" to="0 864 146" dur="18s" repeatCount="indefinite" />
      </circle>
      <ellipse cx="864" cy="146" rx="82" ry="26" fill="none" stroke="{t['violet']}" stroke-width="0.8" stroke-opacity="0.4" transform="rotate(18 864 146)" />
      <path d="{oct_frames[0]}" fill="none" stroke="{t['violet']}" stroke-width="1.3" stroke-opacity="0.6" stroke-linejoin="round">
        <animate attributeName="d" values="{oct_vals}" dur="10s" repeatCount="indefinite" />
      </path>
      <circle cx="864" cy="146" r="3" fill="{t['violet']}" opacity="0.85" />
    </g>
  </g>

  <!-- Outer Card Border + Chamfer Corner Brackets -->
  <rect x="2" y="2" width="996" height="272" rx="14" fill="none" stroke="{t['border']}" stroke-width="1.5" />
  <path d="M 16 32 L 16 16 L 32 16" fill="none" stroke="{t['cyan']}" stroke-width="1.5" stroke-opacity="0.7" />
  <path d="M 984 32 L 984 16 L 968 16" fill="none" stroke="{t['violet']}" stroke-width="1.5" stroke-opacity="0.7" />
  <path d="M 16 244 L 16 260 L 32 260" fill="none" stroke="{t['border_hi']}" stroke-width="1.5" />
  <path d="M 984 244 L 984 260 L 968 260" fill="none" stroke="{t['border_hi']}" stroke-width="1.5" />

  <!-- Top Telemetry Header -->
  <g class="mono" font-size="11" fill="{t['muted']}">
    <circle cx="36" cy="34" r="6" fill="{t['emerald']}" fill-opacity="0.2" class="beacon" />
    <circle cx="36" cy="34" r="3.2" fill="{t['emerald']}" />
    <text x="50" y="38" letter-spacing="1.4" fill="{t['ink2']}" font-weight="600">NODE // HP-0109 • ONLINE</text>
    <text x="500" y="38" text-anchor="middle" letter-spacing="2.2" fill="{t['muted']}">AUTONOMOUS AGENT CORE</text>
    <text x="964" y="38" text-anchor="end" letter-spacing="1.2" fill="{t['ink2']}">SYNCED // {synced}</text>
  </g>
  <line x1="32" y1="54" x2="968" y2="54" stroke="{t['border']}" stroke-width="1" />

  <!-- Center Hero Identity -->
  <text x="500" y="130" text-anchor="middle" class="sans" font-weight="900" font-size="52" letter-spacing="14" fill="url(#titleGrad)">HIEUPEAK</text>
  <line x1="250" y1="154" x2="750" y2="154" stroke="url(#accentBar)" stroke-width="1.5" />
  <polygon points="500,149 505,154 500,159 495,154" fill="{t['cyan']}" />
  <text x="500" y="185" text-anchor="middle" class="mono" font-size="12.5" font-weight="600" letter-spacing="3.2" fill="{t['ink2']}">
    SYSTEMS ARCHITECT • AGENTIC AI • SECURITY &amp; RF ENGINEERING
  </text>
  <text x="500" y="207" text-anchor="middle" class="mono" font-size="10.5" letter-spacing="1.8" fill="{t['muted']}">
    ZERO RUNTIME COMPROMISE • OBSIDIAN TITANIUM DESIGN SYSTEM v2
  </text>

  <!-- Bottom Live Telemetry Strip -->
  <line x1="32" y1="228" x2="968" y2="228" stroke="{t['border']}" stroke-width="1" />
  <g class="mono" font-size="10.5" fill="{t['muted']}">
    <text x="36" y="250" letter-spacing="1.1">CONTRIBS (1Y): <tspan fill="{t['cyan']}" font-weight="700">{c['total_contributions']}</tspan></text>
    <text x="275" y="250" text-anchor="middle" letter-spacing="1.1">ACTIVE DAYS: <tspan fill="{t['ink']}" font-weight="700">{c['active_days']}</tspan></text>
    <text x="500" y="250" text-anchor="middle" letter-spacing="1.1">REPOSITORIES: <tspan fill="{t['ink']}" font-weight="700">{u['public_repos']}</tspan></text>
    <text x="725" y="250" text-anchor="middle" letter-spacing="1.1">STREAK: <tspan fill="{t['emerald']}" font-weight="700">{c['current_streak']}D</tspan> (MAX {c['longest_streak']}D)</text>
    <text x="964" y="250" text-anchor="end" letter-spacing="1.1">STARS: <tspan fill="{t['amber']}" font-weight="700">{u['total_stars']}</tspan></text>
  </g>
</svg>
"""


def build_terminal_marquee(theme_name: str) -> str:
    t = THEMES[theme_name]
    lines = [
        "Distilling agent failure traces into deterministic tool abstractions",
        "Engineering 60 FPS TrueColor ASCII & real-time RF/BLE radar suites",
        "Zero-dependency defensive web security auditing & enterprise hardening",
        "Operating at Apex Flow State • Continuous Iteration • Every Commit",
    ]
    line_els = []
    for idx, txt in enumerate(lines):
        delay = idx * 4
        line_els.append(
            f'<text x="74" y="31" class="mono line line-{idx}" font-size="13.5" font-weight="600" fill="{t["ink"]}" style="animation-delay:{delay}s">{esc(txt)}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 50" width="100%" height="50" role="img" aria-label="Dynamic Command Terminal">
  <style>
    .mono {{ font-family: {FONT_MONO}; }}
    @keyframes cycleLine {{
      0%, 4% {{ opacity: 0; transform: translateY(7px); }}
      8%, 22% {{ opacity: 1; transform: translateY(0px); }}
      26%, 100% {{ opacity: 0; transform: translateY(-7px); }}
    }}
    @keyframes blinkCursor {{
      0%, 49% {{ opacity: 1; }}
      50%, 100% {{ opacity: 0.15; }}
    }}
    .line {{ opacity: 0; animation: cycleLine 16s cubic-bezier(0.22, 1, 0.36, 1) infinite; }}
    .cursor {{ animation: blinkCursor 1.1s steps(2, end) infinite; }}
  </style>
  <rect x="2" y="2" width="996" height="46" rx="10" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1.2" />
  <rect x="14" y="13" width="44" height="24" rx="6" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <text x="36" y="29" text-anchor="middle" class="mono" font-size="11.5" font-weight="700" fill="{t['cyan']}">&gt;_</text>
  {''.join(line_els)}
  <rect x="970" y="16" width="8" height="18" rx="2" fill="{t['cyan']}" class="cursor" />
</svg>
"""


def _smooth_spline_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    if len(points) == 1:
        return f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    d = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d.append(f"C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d)


def build_telemetry_dashboard(data: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    u = data["user"]
    c = data["contributions"]
    langs = data.get("languages", [])[:5]
    weekly = c.get("weekly_counts", [0] * 53)
    weekdays = c.get("weekday_distribution", [])
    peak = c.get("peak_day", {"date": "—", "count": 0})

    # KPI 4 primary language
    top_lang = langs[0]["name"] if langs else "Python"
    top_lang_pct = f"{langs[0]['percent']:.1f}%" if langs else "100%"
    second_lang = f"{langs[1]['percent']:.1f}% {langs[1]['name']}" if len(langs) > 1 else "Pure Stack"

    # Build 52-week velocity chart geometry inside panel (x=28..452, y=176..308)
    chart_x0, chart_y0, chart_w, chart_h = 40, 210, 396, 86
    max_w = max(weekly) if weekly and max(weekly) > 0 else 1
    n_w = len(weekly)
    pts = []
    for i, val in enumerate(weekly):
        px = chart_x0 + (i / max(1, n_w - 1)) * chart_w
        py = chart_y0 + chart_h - (val / max_w) * (chart_h - 10)
        pts.append((px, py))

    # Clamp spline control points so curve never dips below baseline y0+chart_h
    line_path = _smooth_spline_path(pts)
    area_path = f"{line_path} L{pts[-1][0]:.1f},{chart_y0 + chart_h:.1f} L{pts[0][0]:.1f},{chart_y0 + chart_h:.1f} Z" if pts else ""

    # Peak weekly point marker
    peak_w_idx = max(range(n_w), key=lambda i: weekly[i]) if weekly else 0
    peak_pt = pts[peak_w_idx] if pts else (chart_x0, chart_y0 + chart_h)
    peak_w_val = weekly[peak_w_idx] if weekly else 0

    # Month axis ticks for chart
    month_labels_svg = []
    for m in c.get("months", []):
        mx = chart_x0 + (m["col"] / max(1, n_w - 1)) * chart_w
        if mx <= chart_x0 + chart_w - 14:
            month_labels_svg.append(
                f'<text x="{mx:.1f}" y="{chart_y0 + chart_h + 15}" class="mono" font-size="9" fill="{t["muted"]}">{esc(m["label"])}</text>'
            )

    # Stacked Language Bar inside Panel B (x=492..744)
    bar_x, bar_y, bar_w, bar_h = 492, 208, 250, 10
    total_pct = sum(l["percent"] for l in langs) or 100.0
    cur_x = bar_x
    lang_segs = []
    lang_rows = []
    for i, lg in enumerate(langs):
        seg_w = max(2.0, (lg["percent"] / total_pct) * bar_w)
        if i == len(langs) - 1:
            seg_w = max(2.0, (bar_x + bar_w) - cur_x)
        lang_segs.append(
            f'<rect x="{cur_x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{lg["color"]}" />'
        )
        cur_x += seg_w
        ry = 238 + i * 19
        lang_rows.append(f"""
        <circle cx="497" cy="{ry - 3.5}" r="4" fill="{lg['color']}" />
        <text x="508" y="{ry}" class="sans" font-size="11.5" font-weight="600" fill="{t['ink']}">{esc(lg['name'])}</text>
        <text x="742" y="{ry}" text-anchor="end" class="mono" font-size="11" fill="{t['ink2']}">{lg['percent']:.2f}%</text>
        """)

    # Weekly Cadence Histogram inside Panel C (x=786..962)
    wd_max = max((d["count"] for d in weekdays), default=1) or 1
    wd_bars = []
    for i, wd in enumerate(weekdays):
        bx = 790 + i * 24.5
        bh = max(4.0, (wd["count"] / wd_max) * 76.0)
        by = 296 - bh
        is_peak = wd["count"] == wd_max and wd_max > 0
        fill_col = t["cyan"] if is_peak else (t["violet"] if wd["count"] > 0 else t["border"])
        wd_bars.append(f"""
        <rect x="{bx:.1f}" y="220" width="14" height="76" rx="4" fill="{t['panel_alt']}" opacity="0.45" />
        <rect x="{bx:.1f}" y="{by:.1f}" width="14" height="{bh:.1f}" rx="4" fill="{fill_col}" />
        <text x="{bx + 7:.1f}" y="312" text-anchor="middle" class="mono" font-size="9" fill="{t['ink'] if is_peak else t['muted']}">{esc(wd['day'][0])}</text>
        """)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 344" width="100%" height="344" role="img" aria-label="Codebase Telemetry Dashboard">
  <defs>
    <linearGradient id="dashBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t['canvas']}" />
      <stop offset="100%" stop-color="{t['surface']}" />
    </linearGradient>
    <linearGradient id="areaFill" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{t['cyan']}" stop-opacity="0.38" />
      <stop offset="100%" stop-color="{t['cyan']}" stop-opacity="0.01" />
    </linearGradient>
    <clipPath id="langBarClip">
      <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" />
    </clipPath>
    <clipPath id="sparkClip">
      <rect x="{chart_x0}" y="{chart_y0 - 14}" width="{chart_w}" height="{chart_h + 15}" />
    </clipPath>
  </defs>

  <style>
    .mono {{ font-family: {FONT_MONO}; }}
    .sans {{ font-family: {FONT_SANS}; }}
    @keyframes pulseRing {{
      0%, 100% {{ r: 4; opacity: 0.9; }}
      50% {{ r: 8; opacity: 0.25; }}
    }}
    .peak-halo {{ animation: pulseRing 2.4s ease-in-out infinite; }}
  </style>

  <!-- Outer Card -->
  <rect x="2" y="2" width="996" height="340" rx="14" fill="url(#dashBg)" stroke="{t['border']}" stroke-width="1.5" />

  <!-- Header -->
  <text x="26" y="34" class="mono" font-size="11.5" font-weight="700" letter-spacing="1.6" fill="{t['ink']}">TELEMETRY // LIVE CODEBASE ANALYTICS</text>
  <rect x="752" y="18" width="222" height="22" rx="6" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <circle cx="766" cy="29" r="3" fill="{t['emerald']}" />
  <text x="776" y="33" class="mono" font-size="10" fill="{t['ink2']}">GITHUB STREAM • VERIFIED</text>

  <!-- Row 1: 4 KPI Cards -->
  <!-- KPI 1 -->
  <rect x="24" y="54" width="226" height="92" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <rect x="24" y="54" width="226" height="3" rx="1.5" fill="{t['cyan']}" />
  <text x="40" y="78" class="mono" font-size="10" letter-spacing="1.2" fill="{t['muted']}">CONTRIBUTIONS (1Y)</text>
  <text x="40" y="114" class="sans" font-size="30" font-weight="800" fill="{t['ink']}">{c['total_contributions']}</text>
  <text x="40" y="134" class="mono" font-size="10" fill="{t['ink2']}">{c['active_days']} active days • Peak {peak['count']}/day</text>

  <!-- KPI 2 -->
  <rect x="266" y="54" width="226" height="92" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <rect x="266" y="54" width="226" height="3" rx="1.5" fill="{t['emerald']}" />
  <text x="282" y="78" class="mono" font-size="10" letter-spacing="1.2" fill="{t['muted']}">STREAK CADENCE</text>
  <text x="282" y="114" class="sans" font-size="30" font-weight="800" fill="{t['ink']}">{c['current_streak']} <tspan font-size="14" font-weight="600" fill="{t['emerald']}">DAYS</tspan></text>
  <text x="282" y="134" class="mono" font-size="10" fill="{t['ink2']}">Longest: {c['longest_streak']}d • Peak {esc(peak.get('date','—'))}</text>

  <!-- KPI 3 -->
  <rect x="508" y="54" width="226" height="92" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <rect x="508" y="54" width="226" height="3" rx="1.5" fill="{t['violet']}" />
  <text x="524" y="78" class="mono" font-size="10" letter-spacing="1.2" fill="{t['muted']}">REPOS &amp; REPUTATION</text>
  <text x="524" y="114" class="sans" font-size="30" font-weight="800" fill="{t['ink']}">{u['public_repos']} <tspan font-size="14" font-weight="600" fill="{t['violet']}">REPOS</tspan></text>
  <text x="524" y="134" class="mono" font-size="10" fill="{t['ink2']}">{u['total_stars']} stars • {u['followers']} followers</text>

  <!-- KPI 4 -->
  <rect x="750" y="54" width="226" height="92" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <rect x="750" y="54" width="226" height="3" rx="1.5" fill="{t['amber']}" />
  <text x="766" y="78" class="mono" font-size="10" letter-spacing="1.2" fill="{t['muted']}">PRIMARY RUNTIME</text>
  <text x="766" y="114" class="sans" font-size="26" font-weight="800" fill="{t['ink']}">{esc(top_lang)}</text>
  <text x="766" y="134" class="mono" font-size="10" fill="{t['ink2']}">{top_lang_pct} share • {esc(second_lang)}</text>

  <!-- Row 2 Panel A: 52-Week Velocity Curve -->
  <rect x="24" y="162" width="432" height="162" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <text x="40" y="186" class="mono" font-size="10.5" font-weight="700" letter-spacing="1.2" fill="{t['ink']}">52-WEEK COMMIT VELOCITY</text>
  <text x="438" y="186" text-anchor="end" class="mono" font-size="10" fill="{t['cyan']}">PEAK: {peak_w_val}/WK</text>
  <line x1="{chart_x0}" y1="{chart_y0 + chart_h}" x2="{chart_x0 + chart_w}" y2="{chart_y0 + chart_h}" stroke="{t['border']}" stroke-width="1" />
  <line x1="{chart_x0}" y1="{chart_y0 + chart_h / 2}" x2="{chart_x0 + chart_w}" y2="{chart_y0 + chart_h / 2}" stroke="{t['border']}" stroke-width="0.8" stroke-dasharray="3 4" />
  <g clip-path="url(#sparkClip)">
    <path d="{area_path}" fill="url(#areaFill)" />
    <path d="{line_path}" fill="none" stroke="{t['cyan']}" stroke-width="2" stroke-linecap="round" />
  </g>
  <circle cx="{peak_pt[0]:.1f}" cy="{peak_pt[1]:.1f}" r="6" fill="{t['cyan']}" class="peak-halo" />
  <circle cx="{peak_pt[0]:.1f}" cy="{peak_pt[1]:.1f}" r="3.2" fill="{t['ink']}" stroke="{t['cyan']}" stroke-width="1.5" />
  {''.join(month_labels_svg)}

  <!-- Row 2 Panel B: Language Architecture -->
  <rect x="472" y="162" width="290" height="162" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <text x="492" y="186" class="mono" font-size="10.5" font-weight="700" letter-spacing="1.2" fill="{t['ink']}">LANGUAGE MATRIX</text>
  <text x="742" y="186" text-anchor="end" class="mono" font-size="10" fill="{t['muted']}">BYTE-EXACT</text>
  <g clip-path="url(#langBarClip)">
    {''.join(lang_segs)}
  </g>
  {''.join(lang_rows)}

  <!-- Row 2 Panel C: Weekly Cadence -->
  <rect x="778" y="162" width="198" height="162" rx="10" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <text x="794" y="186" class="mono" font-size="10.5" font-weight="700" letter-spacing="1.2" fill="{t['ink']}">CADENCE</text>
  <text x="960" y="186" text-anchor="end" class="mono" font-size="10" fill="{t['muted']}">MON–SUN</text>
  {''.join(wd_bars)}
</svg>
"""


REPO_ICONS = {
    "Failure-to-Tool-Distiller": '<path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="COLOR" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="3.5" fill="none" stroke="COLOR" stroke-width="1.8"/>',
    "Video-to-ASCII": '<rect x="3" y="4" width="18" height="14" rx="2" fill="none" stroke="COLOR" stroke-width="1.8"/><path d="M10 9l5 3-5 3V9z" fill="COLOR"/><path d="M7 21h10" stroke="COLOR" stroke-width="1.8" stroke-linecap="round"/>',
    "Scann-the-device": '<circle cx="12" cy="12" r="9" fill="none" stroke="COLOR" stroke-width="1.6" stroke-opacity="0.45"/><circle cx="12" cy="12" r="5" fill="none" stroke="COLOR" stroke-width="1.6" stroke-opacity="0.75"/><circle cx="12" cy="12" r="2" fill="COLOR"/><path d="M12 12l6-6" stroke="COLOR" stroke-width="1.8" stroke-linecap="round"/>',
    "security-check": '<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3z" fill="none" stroke="COLOR" stroke-width="1.8" stroke-linejoin="round"/><path d="M9.5 12l2 2 3.5-3.5" fill="none" stroke="COLOR" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "LYRIC-DISCORD": '<path d="M9 18V6l10-2v12" fill="none" stroke="COLOR" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="6.5" cy="18" r="2.5" fill="none" stroke="COLOR" stroke-width="1.8"/><circle cx="16.5" cy="16" r="2.5" fill="none" stroke="COLOR" stroke-width="1.8"/>',
    "key-fast-for-c-": '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="none" stroke="COLOR" stroke-width="1.8" stroke-linejoin="round"/>',
}


def build_repo_card(repo: dict, idx: int, theme_name: str) -> str:
    t = THEMES[theme_name]
    accent = repo.get("language_color") or t["cyan"]
    icon_raw = REPO_ICONS.get(repo["name"], REPO_ICONS["Failure-to-Tool-Distiller"]).replace("COLOR", accent)
    wrapped = textwrap.wrap(repo["description"], width=56)[:2]
    if len(textwrap.wrap(repo["description"], width=56)) > 2:
        wrapped[1] = wrapped[1][:52].rstrip() + "..."
    line1 = esc(wrapped[0]) if len(wrapped) > 0 else ""
    line2 = esc(wrapped[1]) if len(wrapped) > 1 else ""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 490 154" width="100%" height="154" role="img" aria-label="{esc(repo['name'])}">
  <style>
    .mono {{ font-family: {FONT_MONO}; }}
    .sans {{ font-family: {FONT_SANS}; }}
  </style>
  <rect x="2" y="2" width="486" height="150" rx="12" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1.4" />
  <rect x="24" y="2" width="120" height="2.5" rx="1" fill="{accent}" />

  <!-- Icon Container -->
  <rect x="20" y="20" width="34" height="34" rx="8" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <g transform="translate(25, 25)">{icon_raw}</g>

  <!-- Title & Index -->
  <text x="66" y="34" class="sans" font-size="15.5" font-weight="700" fill="{t['ink']}">{esc(repo['name'])}</text>
  <text x="66" y="50" class="mono" font-size="10" fill="{t['muted']}">MOD // 0{idx + 1} • PUBLIC REPOSITORY</text>

  <!-- Top-Right Launch Arrow -->
  <rect x="442" y="20" width="28" height="28" rx="7" fill="{t['panel']}" stroke="{t['border']}" stroke-width="1" />
  <path d="M452 38l8-8m0 0h-6m6 0v6" fill="none" stroke="{t['ink2']}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />

  <!-- Description -->
  <text x="20" y="80" class="sans" font-size="12.5" fill="{t['ink2']}">{line1}</text>
  <text x="20" y="99" class="sans" font-size="12.5" fill="{t['ink2']}">{line2}</text>

  <!-- Bottom Meta Bar -->
  <line x1="20" y1="118" x2="470" y2="118" stroke="{t['border']}" stroke-width="1" />
  <circle cx="27" cy="134" r="4.5" fill="{accent}" />
  <text x="38" y="138" class="mono" font-size="11" font-weight="600" fill="{t['ink']}">{esc(repo['language'])}</text>
  <text x="155" y="138" class="mono" font-size="11" fill="{t['amber']}">★ {repo['stars']}</text>
  <text x="215" y="138" class="mono" font-size="11" fill="{t['muted']}">⑂ {repo['forks']}</text>
  <text x="470" y="138" text-anchor="end" class="mono" font-size="10.5" font-weight="600" fill="{accent}">INSPECT →</text>
</svg>
"""


def build_pill_badge(label: str, value: str, accent_key: str, icon_svg: str, theme_name: str, pulse: bool = False) -> str:
    t = THEMES[theme_name]
    accent = t.get(accent_key, accent_key)
    label_w = max(58, len(label) * 7.8 + 32)
    val_w = max(68, len(value) * 8.1 + 24)
    total_w = int(label_w + val_w)
    pulse_dot = f'<circle cx="14" cy="16" r="3" fill="{accent}" />' if not pulse else f'<circle cx="14" cy="16" r="5" fill="{accent}" fill-opacity="0.25"><animate attributeName="r" values="3.5;6.5;3.5" dur="2s" repeatCount="indefinite"/></circle><circle cx="14" cy="16" r="3" fill="{accent}"/>'
    icon_block = f'<g transform="translate(8, 8)">{icon_svg.replace("COLOR", accent)}</g>' if icon_svg else pulse_dot
    text_x = 30 if icon_svg else 25
    if icon_svg:
        label_w = max(label_w, len(label) * 7.8 + 36)
        total_w = int(label_w + val_w)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 32" width="{total_w}" height="32" role="img" aria-label="{esc(label)}: {esc(value)}">
  <style>
    .mono {{ font-family: {FONT_MONO}; }}
  </style>
  <defs>
    <clipPath id="pclip"><rect x="1" y="1" width="{total_w - 2}" height="30" rx="8" /></clipPath>
  </defs>
  <g clip-path="url(#pclip)">
    <rect x="1" y="1" width="{int(label_w)}" height="30" fill="{t['pill_label']}" />
    <rect x="{int(label_w)}" y="1" width="{int(val_w)}" height="30" fill="{t['pill_bg']}" />
    <line x1="{int(label_w)}" y1="1" x2="{int(label_w)}" y2="31" stroke="{t['border']}" stroke-width="1" />
  </g>
  <rect x="1" y="1" width="{total_w - 2}" height="30" rx="8" fill="none" stroke="{t['border']}" stroke-width="1.2" />
  {icon_block}
  <text x="{text_x}" y="20" class="mono" font-size="10.5" font-weight="600" letter-spacing="0.8" fill="{t['ink2']}">{esc(label)}</text>
  <text x="{int(label_w + val_w / 2)}" y="20" text-anchor="middle" class="mono" font-size="10.5" font-weight="700" letter-spacing="0.8" fill="{t['ink']}">{esc(value)}</text>
</svg>
"""


def build_audio_deck(theme_name: str) -> str:
    t = THEMES[theme_name]
    bars = []
    heights = [10, 22, 16, 28, 14, 24, 30, 18, 12, 26, 20, 32, 15, 25, 19, 29, 13, 22, 27, 16, 24, 12, 20, 14]
    for i, h in enumerate(heights):
        bx = 708 + i * 11
        by = 44 - h / 2
        dur = 0.75 + (i % 5) * 0.16
        col = t["cyan"] if i % 3 == 0 else (t["violet"] if i % 3 == 1 else t["ink2"])
        bars.append(
            f'<rect x="{bx}" y="{by:.1f}" width="5.5" height="{h}" rx="2.5" fill="{col}" opacity="0.85">'
            f'<animate attributeName="height" values="{max(6, h-10)};{min(34, h+6)};{max(6, h-10)}" dur="{dur:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{44 - max(6, h-10)/2:.1f};{44 - min(34, h+6)/2:.1f};{44 - max(6, h-10)/2:.1f}" dur="{dur:.2f}s" repeatCount="indefinite"/>'
            f'</rect>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 88" width="100%" height="88" role="img" aria-label="Soundscape Deep Work Flow State">
  <style>
    .mono {{ font-family: {FONT_MONO}; }}
    .sans {{ font-family: {FONT_SANS}; }}
  </style>
  <rect x="2" y="2" width="996" height="84" rx="12" fill="{t['surface']}" stroke="{t['border']}" stroke-width="1.4" />

  <!-- Disc Icon -->
  <circle cx="48" cy="44" r="22" fill="{t['panel']}" stroke="{t['border_hi']}" stroke-width="1.5" />
  <circle cx="48" cy="44" r="14" fill="none" stroke="{t['cyan']}" stroke-width="1.2" stroke-dasharray="6 4">
    <animateTransform attributeName="transform" type="rotate" from="0 48 44" to="360 48 44" dur="6s" repeatCount="indefinite" />
  </circle>
  <polygon points="44,37 56,44 44,51" fill="{t['ink']}" />

  <!-- Track Text -->
  <text x="88" y="34" class="mono" font-size="10.5" font-weight="700" letter-spacing="1.4" fill="{t['cyan']}">SOUNDSCAPE // DEEP WORK FLOW STATE</text>
  <text x="88" y="54" class="sans" font-size="14" font-weight="600" fill="{t['ink']}">Dark Ambient • Minimalist Techno • Cyber Synth OST</text>

  <!-- Scrubber -->
  <rect x="88" y="65" width="380" height="4" rx="2" fill="{t['panel_alt']}" />
  <rect x="88" y="65" width="268" height="4" rx="2" fill="{t['cyan']}">
    <animate attributeName="width" values="180;340;180" dur="18s" repeatCount="indefinite" />
  </rect>
  <text x="480" y="70" class="mono" font-size="10" fill="{t['muted']}">320KBPS LOSSLESS STREAM</text>

  <!-- Equalizer -->
  {''.join(bars)}
</svg>
"""


def build_divider(theme_name: str) -> str:
    t = THEMES[theme_name]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 14" width="100%" height="14" role="img" aria-label="Divider">
  <defs>
    <linearGradient id="divLine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['border']}" stop-opacity="0" />
      <stop offset="25%" stop-color="{t['border_hi']}" />
      <stop offset="50%" stop-color="{t['cyan']}" stop-opacity="0.7" />
      <stop offset="75%" stop-color="{t['border_hi']}" />
      <stop offset="100%" stop-color="{t['border']}" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="pulseBar" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['cyan']}" stop-opacity="0" />
      <stop offset="50%" stop-color="{t['cyan']}" stop-opacity="1" />
      <stop offset="100%" stop-color="{t['cyan']}" stop-opacity="0" />
    </linearGradient>
  </defs>
  <rect x="0" y="6" width="1000" height="1.5" fill="url(#divLine)" />
  <rect x="-140" y="5.5" width="140" height="2.5" rx="1.2" fill="url(#pulseBar)">
    <animate attributeName="x" values="-140;1000" dur="4.5s" repeatCount="indefinite" />
  </rect>
  <polygon points="500,3 504,7 500,11 496,7" fill="{t['cyan']}" opacity="0.85" />
</svg>
"""


def build_footer(data: dict, theme_name: str) -> str:
    t = THEMES[theme_name]
    synced = esc(data.get("synced_at", "2026"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 88" width="100%" height="88" role="img" aria-label="HieuPeak Footer">
  <defs>
    <linearGradient id="fBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t['canvas']}" />
      <stop offset="50%" stop-color="{t['surface']}" />
      <stop offset="100%" stop-color="{t['canvas']}" />
    </linearGradient>
    <linearGradient id="fLine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['border']}" stop-opacity="0" />
      <stop offset="50%" stop-color="{t['cyan']}" stop-opacity="0.7" />
      <stop offset="100%" stop-color="{t['border']}" stop-opacity="0" />
    </linearGradient>
  </defs>
  <style>
    .mono {{ font-family: {FONT_MONO}; }}
  </style>
  <rect x="2" y="2" width="996" height="84" rx="14" fill="url(#fBg)" stroke="{t['border']}" stroke-width="1.4" />
  <line x1="120" y1="2" x2="880" y2="2" stroke="url(#fLine)" stroke-width="2" />
  <path d="M 16 26 L 16 14 L 28 14" fill="none" stroke="{t['border_hi']}" stroke-width="1.4" />
  <path d="M 984 26 L 984 14 L 972 14" fill="none" stroke="{t['border_hi']}" stroke-width="1.4" />
  <text x="500" y="38" text-anchor="middle" class="mono" font-size="11.5" font-weight="700" letter-spacing="2.8" fill="{t['ink']}">
    HIEUPEAK // ZERO RUNTIME COMPROMISE • OBSIDIAN TITANIUM ARCHITECTURE
  </text>
  <text x="500" y="60" text-anchor="middle" class="mono" font-size="10" letter-spacing="1.6" fill="{t['muted']}">
    ALL SYSTEMS NOMINAL • CONTINUOUS CI/CD TELEMETRY • LAST SYNC {synced}
  </text>
</svg>
"""


SOCIAL_BADGE_SPECS = [
    ("guns", "GUNS.LOL", "hieupeak", "cyan", '<circle cx="8" cy="8" r="5.5" fill="none" stroke="COLOR" stroke-width="1.5"/><circle cx="8" cy="8" r="1.8" fill="COLOR"/><path d="M8 1v2.5M8 12.5V15M1 8h2.5M12.5 8H15" stroke="COLOR" stroke-width="1.4" stroke-linecap="round"/>'),
    ("discord", "DISCORD", "hieutoilet.m", "violet", '<path d="M3 4.5c2-.9 4-.9 5-.9s3 0 5 .9c1 2.2 1.2 4.8.7 6.9-1.2.9-2.5 1.3-3.7 1.6l-.7-1.1c.6-.2 1.1-.5 1.6-.9-.3-.2-.6-.4-.9-.5-1.3.6-2.7.6-4 0-.3.1-.6.3-.9.5.5.4 1 .7 1.6.9l-.7 1.1c-1.2-.3-2.5-.7-3.7-1.6-.5-2.1-.3-4.7.7-6.9z" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linejoin="round"/><circle cx="6" cy="8.2" r="1" fill="COLOR"/><circle cx="10" cy="8.2" r="1" fill="COLOR"/>'),
    ("xbox", "XBOX", "Hieupeak7238", "emerald", '<circle cx="8" cy="8" r="6" fill="none" stroke="COLOR" stroke-width="1.5"/><path d="M4.2 4.6C6 6.2 10 9.8 11.8 11.4M11.8 4.6C10 6.2 6 9.8 4.2 11.4" stroke="COLOR" stroke-width="1.5" stroke-linecap="round"/>'),
    ("tiktok", "TIKTOK", "@nhh2ler11", "rose", '<path d="M9.5 2.5v7.8a2.8 2.8 0 1 1-2.2-2.7" fill="none" stroke="COLOR" stroke-width="1.6" stroke-linecap="round"/><path d="M9.5 2.5c.7 1.7 2 2.6 3.5 2.8" fill="none" stroke="COLOR" stroke-width="1.6" stroke-linecap="round"/>'),
    ("reddit", "REDDIT", "Hieupeak0109", "amber", '<ellipse cx="8" cy="9.5" rx="5.5" ry="3.8" fill="none" stroke="COLOR" stroke-width="1.4"/><path d="M8 5.7L9.3 2.5l2.5.6" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linecap="round"/><circle cx="12.3" cy="3.2" r="1" fill="COLOR"/><circle cx="6" cy="9.2" r="0.9" fill="COLOR"/><circle cx="10" cy="9.2" r="0.9" fill="COLOR"/>'),
    ("facebook", "FACEBOOK", "Hieupeak", "cyan", '<circle cx="8" cy="8" r="6" fill="none" stroke="COLOR" stroke-width="1.4"/><path d="M9.8 4.8H8.6c-.7 0-1 .4-1 1.1v7.6M6.2 8.4h3.2" fill="none" stroke="COLOR" stroke-width="1.5" stroke-linecap="round"/>'),
]

STATUS_BADGE_SPECS = [
    ("status-operational", "STATUS", "OPERATIONAL", "emerald", "", True),
    ("engine-agentic", "ENGINE", "AGENTIC AI", "cyan", '<circle cx="8" cy="8" r="2.2" fill="COLOR"/><path d="M8 2.2v2.2M8 11.6v2.2M2.2 8h2.2M11.6 8h2.2M3.9 3.9l1.6 1.6M10.5 10.5l1.6 1.6M12.1 3.9l-1.6 1.6M5.5 10.5l-1.6 1.6" stroke="COLOR" stroke-width="1.4" stroke-linecap="round"/>', False),
    ("flow-velocity", "FLOW", "HYPER VELOCITY", "violet", '<path d="M9 1.8L3.5 9.2H8l-1 5 5.5-7.4H8l1-5z" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linejoin="round"/>', False),
    ("rig-titanium", "RIG SPEC", "WIN11 • ARCH", "amber", '<rect x="2.2" y="2.8" width="11.6" height="10.4" rx="2" fill="none" stroke="COLOR" stroke-width="1.4"/><path d="M5 6.5l2 1.8-2 1.8M8.5 10.1h2.5" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>', False),
    ("auth-verified", "IDENTITY", "VERIFIED", "emerald", '<path d="M8 2l5 2v4c0 3.2-2.2 5.7-5 6.8-2.8-1.1-5-3.6-5-6.8V4l5-2z" fill="none" stroke="COLOR" stroke-width="1.4"/><path d="M5.8 8.2l1.6 1.6 3-3" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linecap="round"/>', False),
    ("rank-apex", "RANK", "APEX PREDATOR", "rose", '<path d="M8 2l4.8 10.5L8 10l-4.8 2.5L8 2z" fill="none" stroke="COLOR" stroke-width="1.4" stroke-linejoin="round"/>', False),
    ("class-architect", "CLASS", "SYS ARCHITECT", "cyan", '<polygon points="8,2 13.5,5.2 13.5,10.8 8,14 2.5,10.8 2.5,5.2" fill="none" stroke="COLOR" stroke-width="1.4"/><circle cx="8" cy="8" r="1.6" fill="COLOR"/>', False),
]


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_all_svgs(repo_root: str, data: dict):
    assets = os.path.join(repo_root, "assets")
    cards_dir = os.path.join(assets, "cards")
    badges_dir = os.path.join(assets, "badges")
    os.makedirs(cards_dir, exist_ok=True)
    os.makedirs(badges_dir, exist_ok=True)

    for theme_name in ("dark", "light"):
        suffix = "" if theme_name == "dark" else "-light"
        _write(os.path.join(assets, f"banner{suffix}.svg"), build_banner(data, theme_name))
        _write(os.path.join(assets, f"terminal-marquee{suffix}.svg"), build_terminal_marquee(theme_name))
        _write(os.path.join(assets, f"telemetry-dashboard{suffix}.svg"), build_telemetry_dashboard(data, theme_name))
        _write(os.path.join(assets, f"audio-deck{suffix}.svg"), build_audio_deck(theme_name))
        _write(os.path.join(assets, f"divider{suffix}.svg"), build_divider(theme_name))
        _write(os.path.join(assets, f"footer{suffix}.svg"), build_footer(data, theme_name))

        for idx, repo in enumerate(data.get("featured_repos", [])[:6]):
            slug = repo["name"].lower()
            _write(os.path.join(cards_dir, f"repo-{slug}{suffix}.svg"), build_repo_card(repo, idx, theme_name))

        for bid, label, val, acc, icon in SOCIAL_BADGE_SPECS:
            _write(os.path.join(badges_dir, f"{bid}{suffix}.svg"), build_pill_badge(label, val, acc, icon, theme_name))

        for bid, label, val, acc, icon, pulse in STATUS_BADGE_SPECS:
            _write(os.path.join(badges_dir, f"{bid}{suffix}.svg"), build_pill_badge(label, val, acc, icon, theme_name, pulse=pulse))

    print(f"[svg_engine] Generated dark & light SVG suite in {assets}")


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "assets", "profile-data.json"), "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    generate_all_svgs(root, profile_data)
