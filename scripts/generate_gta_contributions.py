import json
import math
import os
import shutil
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from github_data import collect_and_save

USERNAME = os.environ.get("GITHUB_USERNAME", "hieupeakday0109-ai")


def _load_font(size: int, bold: bool = False):
    candidates = (
        [
            r"C:\Windows\Fonts\consolab.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ]
        if bold
        else [
            r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
    )
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _catmull_rom_chain(pts: list[tuple[float, float]], samples_per_seg: int = 24) -> list[tuple[float, float]]:
    if len(pts) < 2:
        return pts
    padded = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for s in range(samples_per_seg):
            t = s / float(samples_per_seg)
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(pts[-1])
    return out


def _build_dynamic_path(cells: list[dict], get_center, width: int, total_frames: int):
    # Extract active cells and group by column clusters so car hits real commit coordinates
    active = [c for c in cells if c["level"] > 0 or c["count"] > 0]
    by_col = {}
    for c in active:
        by_col.setdefault(c["col"], []).append(c)

    ctrl_pts = []
    start_y = get_center(0, 3)[1]
    ctrl_pts.append((12.0, start_y))  # Frame 0: nose already entering left gate

    if not by_col:
        # Fallback graceful slalom if user has 0 commits in window
        for col, row in [(10, 2), (22, 4.5), (35, 1.5), (46, 4), (52, 3)]:
            ctrl_pts.append(get_center(col, row))
    else:
        sorted_cols = sorted(by_col.keys())
        # Add subtle apex entry before first active column if far right
        first_col = sorted_cols[0]
        if first_col > 12:
            ctrl_pts.append(get_center(first_col // 2, 2.2))

        for i, col in enumerate(sorted_cols):
            group = sorted(by_col[col], key=lambda item: item["row"])
            if len(group) == 1:
                ctrl_pts.append(get_center(col, group[0]["row"]))
            else:
                # Visit extreme rows inside the same week column for dramatic drift
                if i % 2 == 0:
                    ctrl_pts.append(get_center(col, group[0]["row"]))
                    ctrl_pts.append(get_center(col, group[-1]["row"]))
                else:
                    ctrl_pts.append(get_center(col, group[-1]["row"]))
                    ctrl_pts.append(get_center(col, group[0]["row"]))

    last_y = ctrl_pts[-1][1]
    ctrl_pts.append((width + 110.0, last_y))

    dense = _catmull_rom_chain(ctrl_pts, samples_per_seg=28)

    # Arc-length parameterization for uniform speed with slight apex slowdown & exit boost
    cum = [0.0]
    for i in range(1, len(dense)):
        dx = dense[i][0] - dense[i - 1][0]
        dy = dense[i][1] - dense[i - 1][1]
        cum.append(cum[-1] + math.hypot(dx, dy))
    total_len = cum[-1] or 1.0

    # Sample evenly at total_frames points (smooth easing near start & nitro finish)
    samples = []
    for f in range(total_frames):
        u = f / float(total_frames - 1)
        # Mild acceleration at exit
        s_target = (0.92 * u + 0.08 * (u * u * u)) * total_len
        idx = int(np.searchsorted(cum, s_target, side="right")) - 1
        idx = max(0, min(len(dense) - 2, idx))
        seg_len = cum[idx + 1] - cum[idx]
        alpha = (s_target - cum[idx]) / seg_len if seg_len > 1e-6 else 0.0
        x = dense[idx][0] + (dense[idx + 1][0] - dense[idx][0]) * alpha
        y = dense[idx][1] + (dense[idx + 1][1] - dense[idx][1]) * alpha
        samples.append((x, y))

    # Compute smoothed heading and drift slip angle from curvature
    path = []
    for f in range(total_frames):
        p_prev = samples[max(0, f - 2)]
        p_next = samples[min(total_frames - 1, f + 2)]
        dx = p_next[0] - p_prev[0]
        dy = p_next[1] - p_prev[1]
        heading = math.degrees(math.atan2(dy, dx))

        # Curvature proxy for drift slip angle
        p_a = samples[max(0, f - 4)]
        p_b = samples[f]
        p_c = samples[min(total_frames - 1, f + 4)]
        h1 = math.atan2(p_b[1] - p_a[1], p_b[0] - p_a[0]) if f >= 2 else math.radians(heading)
        h2 = math.atan2(p_c[1] - p_b[1], p_c[0] - p_b[0]) if f <= total_frames - 3 else math.radians(heading)
        d_ang = math.degrees(math.atan2(math.sin(h2 - h1), math.cos(h2 - h1)))
        slip = max(-28.0, min(28.0, d_ang * 1.45))

        # Velocity in MPH
        step_dist = math.hypot(
            samples[min(total_frames - 1, f + 1)][0] - samples[max(0, f - 1)][0],
            samples[min(total_frames - 1, f + 1)][1] - samples[max(0, f - 1)][1],
        )
        mph = int(min(228, max(118, 138 + step_dist * 2.1 - abs(slip) * 0.8 + (28 if f > total_frames - 22 else 0))))
        path.append((samples[f][0], samples[f][1], heading, slip, mph))

    return path


def _make_headlight_sprite(scale: int = 2) -> Image.Image:
    # Pre-rendered smooth radial-axial volumetric headlight cone (no jagged triangle cutoff!)
    w, h = 210 * scale, 130 * scale
    yy, xx = np.mgrid[0:h, 0:w]
    ox, oy = 6.0 * scale, h / 2.0
    dx = np.maximum(0.0, xx - ox)
    dy = yy - oy
    dist = np.hypot(dx, dy)
    ang = np.abs(np.arctan2(dy, np.maximum(1.0, dx)))
    # Smooth axial fade + angular cone mask
    axial = np.exp(-dist / (82.0 * scale)) * np.clip(1.0 - dist / (195.0 * scale), 0.0, 1.0)
    cone = np.clip(1.0 - (ang / 0.34) ** 2.2, 0.0, 1.0)
    mask = np.where(xx >= ox, axial * cone, 0.0)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 215
    rgba[..., 1] = 242
    rgba[..., 2] = 255
    rgba[..., 3] = np.clip(mask * 125, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def build_animation(data: dict | None = None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    assets_dir = os.path.join(repo_root, "assets")
    temp_dir = os.path.join(repo_root, ".gta_temp")
    frames_dir = os.path.join(temp_dir, "frames")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)

    if data is None:
        json_path = os.path.join(assets_dir, "profile-data.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = collect_and_save(repo_root)

    contrib = data["contributions"]
    cells = contrib["cells"]
    months = contrib.get("months", [])
    total_contributions = contrib.get("total_contributions", 0)
    active_days = contrib.get("active_days", 0)
    max_level = contrib.get("max_level", 4)

    # 2x Supersampled Canvas -> downsampled to 920x280 for razor-sharp visuals
    S = 2
    out_w, out_h = 920, 280
    W, H = out_w * S, out_h * S

    grid_x0 = 72 * S
    grid_y0 = 92 * S
    cell_w, cell_h = 11 * S, 11 * S
    gap = 3 * S
    pitch = cell_w + gap

    font_sm = _load_font(10 * S)
    font_md = _load_font(11 * S, bold=True)
    font_lg = _load_font(13 * S, bold=True)

    # Load car sprite (2x scaled cleanly)
    car_path = os.path.join(assets_dir, "car_sprite.png")
    car_src = Image.open(car_path).convert("RGBA")
    car_scaled = car_src.resize((60 * S, 25 * S), Image.Resampling.LANCZOS)

    # Pre-build underglow & headlight cone sprites
    headlight_sprite = _make_headlight_sprite(S)
    underglow_sprite = Image.new("RGBA", (86 * S, 46 * S), (0, 0, 0, 0))
    ug_draw = ImageDraw.Draw(underglow_sprite)
    ug_draw.ellipse([8 * S, 8 * S, 78 * S, 38 * S], fill=(56, 189, 248, 85))
    underglow_sprite = underglow_sprite.filter(ImageFilter.GaussianBlur(radius=7 * S))

    bg_outer = (7, 7, 9, 255)
    bg_card = (11, 12, 18, 255)
    border_col = (35, 36, 48, 255)
    cell_empty = (20, 22, 32, 255)
    cell_border = (34, 37, 52, 255)

    color_levels = {
        1: (56, 189, 248),   # Cyan #38bdf8
        2: (139, 92, 246),   # Violet #8b5cf6
        3: (244, 63, 94),    # Rose #f43f5e
        4: (251, 191, 36),   # Amber #fbbf24
    }

    # Build static base canvas once for huge speedup & ultra-clean grid
    base = Image.new("RGBA", (W, H), bg_outer)
    bdraw = ImageDraw.Draw(base)
    bdraw.rounded_rectangle([2 * S, 2 * S, W - 2 * S, H - 2 * S], radius=14 * S, fill=bg_card, outline=border_col, width=max(1, int(1.5 * S)))

    # Subtle architectural micro-grid strictly inside the highway arena (pre-blended solid RGB)
    for gy in range(60 * S, 232 * S, 24 * S):
        bdraw.line([(20 * S, gy), (W - 20 * S, gy)], fill=(18, 20, 29, 255), width=max(1, S // 2))
    for gx in range(28 * S, W - 20 * S, 24 * S):
        bdraw.line([(gx, 54 * S), (gx, 232 * S)], fill=(18, 20, 29, 255), width=max(1, S // 2))

    # Corner chamfer highlights (composited via overlay so alpha blends properly)
    corners_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(corners_layer)
    cdraw.line([(16 * S, 16 * S), (32 * S, 16 * S)], fill=(56, 189, 248, 210), width=2 * S)
    cdraw.line([(16 * S, 16 * S), (16 * S, 32 * S)], fill=(56, 189, 248, 210), width=2 * S)
    cdraw.line([(W - 16 * S, 16 * S), (W - 32 * S, 16 * S)], fill=(139, 92, 246, 210), width=2 * S)
    cdraw.line([(W - 16 * S, 16 * S), (W - 16 * S, 32 * S)], fill=(139, 92, 246, 210), width=2 * S)
    base.alpha_composite(corners_layer)
    bdraw = ImageDraw.Draw(base)

    # Header bar
    bdraw.ellipse([28 * S, 23 * S, 37 * S, 32 * S], fill=(16, 185, 129, 255))
    bdraw.text((46 * S, 21 * S), f"APEX GT-01 // @{USERNAME} • CONTRIBUTION HIGHWAY", fill=(248, 250, 252), font=font_lg)
    right_hdr = f"{total_contributions} CONTRIBS • {active_days} ACTIVE DAYS • PEAK LVL {max_level}"
    bbox = bdraw.textbbox((0, 0), right_hdr, font=font_md)
    bdraw.text((W - 32 * S - (bbox[2] - bbox[0]), 23 * S), right_hdr, fill=(148, 163, 184), font=font_md)
    bdraw.line([(30 * S, 50 * S), (W - 30 * S, 50 * S)], fill=border_col, width=S)

    # Month labels
    for m in months:
        mx = grid_x0 + m["col"] * pitch
        if mx < W - 54 * S:
            bdraw.text((mx, 66 * S), m["label"], fill=(113, 113, 122), font=font_sm)

    # Day labels
    for r_idx, d_name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        dy = grid_y0 + r_idx * pitch
        bdraw.text((32 * S, dy), d_name, fill=(82, 82, 91), font=font_sm)

    # Bottom HUD divider + static legend
    bdraw.line([(30 * S, 236 * S), (W - 30 * S, 236 * S)], fill=border_col, width=S)
    leg_x = W - 186 * S
    bdraw.text((leg_x, 248 * S), "Less", fill=(113, 113, 122), font=font_sm)
    leg_x += 32 * S
    bdraw.rounded_rectangle([leg_x, 249 * S, leg_x + 10 * S, 259 * S], radius=2 * S, fill=cell_empty, outline=cell_border, width=S)
    leg_x += 14 * S
    for lvl in [1, 2, 3, 4]:
        bdraw.rounded_rectangle([leg_x, 249 * S, leg_x + 10 * S, 259 * S], radius=2 * S, fill=color_levels[lvl])
        leg_x += 14 * S
    bdraw.text((leg_x + 4 * S, 248 * S), "More", fill=(113, 113, 122), font=font_sm)

    def get_rc_center(c, r):
        return grid_x0 + c * pitch + cell_w / 2.0, grid_y0 + r * pitch + cell_h / 2.0

    total_frames = 120
    path = _build_dynamic_path(cells, get_rc_center, W, total_frames)

    rng = np.random.default_rng(109)
    tracks_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tracks_draw = ImageDraw.Draw(tracks_layer)

    activated_frame = {}
    smoke_particles = []
    tail_history = []
    prev_t1, prev_t2 = None, None

    grid_lookup = {(c["col"], c["row"]): c for c in cells}

    for f_idx in range(total_frames):
        frame = base.copy()
        draw = ImageDraw.Draw(frame)

        car_x, car_y, heading, slip, mph = path[f_idx]
        total_angle = heading + slip
        rad = math.radians(total_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        # Ignite active cells cleanly as the car reaches their column or proximity
        for (c, r), cdata in grid_lookup.items():
            if cdata["level"] <= 0 and cdata["count"] <= 0:
                continue
            cx, cy = get_rc_center(c, r)
            dist = math.hypot(car_x - cx, car_y - cy)
            if car_x >= cx - 10 * S or dist <= 32 * S:
                if (c, r) not in activated_frame:
                    activated_frame[(c, r)] = f_idx

        # Draw grid cells
        for (c, r), cdata in grid_lookup.items():
            x1 = grid_x0 + c * pitch
            y1 = grid_y0 + r * pitch
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            lvl = max(1, cdata["level"]) if cdata["count"] > 0 else cdata["level"]

            if (c, r) in activated_frame:
                age = f_idx - activated_frame[(c, r)]
                base_col = color_levels.get(lvl, color_levels[1])
                if age < 6:
                    # Ignition shockwave ring + crisp flash
                    ring_r = int((3 + age * 2.8) * S)
                    ring_alpha = max(0, 180 - age * 28)
                    draw.rounded_rectangle(
                        [x1 - ring_r // 2, y1 - ring_r // 2, x2 + ring_r // 2, y2 + ring_r // 2],
                        radius=4 * S,
                        outline=(base_col[0], base_col[1], base_col[2], ring_alpha),
                        width=max(1, S),
                    )
                    flash = max(0.0, 1.0 - age / 5.0)
                    col = tuple(int(base_col[k] + (255 - base_col[k]) * flash * 0.75) for k in range(3))
                else:
                    if lvl == 4:
                        pulse = int(16 * math.sin(f_idx * 0.32))
                        col = (min(255, base_col[0] + pulse), min(255, base_col[1] + pulse), base_col[2])
                    else:
                        col = base_col
                    # Subtle ambient glow behind lit cell
                    draw.rounded_rectangle(
                        [x1 - 2 * S, y1 - 2 * S, x2 + 2 * S, y2 + 2 * S],
                        radius=3 * S,
                        fill=(base_col[0], base_col[1], base_col[2], 68),
                    )
                draw.rounded_rectangle([x1, y1, x2, y2], radius=2.5 * S, fill=col)
            else:
                # Subtle ambient outline so upcoming active cells hint faintly under scan
                outline = cell_border
                fill = cell_empty
                if lvl > 0:
                    bc = color_levels.get(lvl, color_levels[1])
                    fill = (24, 27, 40, 255)
                    outline = (bc[0], bc[1], bc[2], 55)
                draw.rounded_rectangle([x1, y1, x2, y2], radius=2.5 * S, fill=fill, outline=outline, width=S)

        # Tire drift skid marks + smoke particles
        if -40 * S < car_x < W + 40 * S:
            t1 = (car_x - 20 * S * cos_a - 9 * S * sin_a, car_y - 20 * S * sin_a + 9 * S * cos_a)
            t2 = (car_x - 20 * S * cos_a + 9 * S * sin_a, car_y - 20 * S * sin_a - 9 * S * cos_a)
            tail_history.append((t1, t2))
            if len(tail_history) > 12:
                tail_history.pop(0)

            if abs(slip) > 5.0:
                if prev_t1 and prev_t2:
                    tracks_draw.line([prev_t1, t1], fill=(56, 189, 248, 36), width=2 * S)
                    tracks_draw.line([prev_t2, t2], fill=(56, 189, 248, 36), width=2 * S)
                if f_idx % 2 == 0:
                    for tx, ty in (t1, t2):
                        smoke_particles.append([
                            tx,
                            ty,
                            (-cos_a * 1.3 + rng.uniform(-0.35, 0.35)) * S,
                            (-sin_a * 1.3 + rng.uniform(-0.35, 0.35)) * S,
                            2.8 * S,
                            0,
                            14,
                        ])
            prev_t1, prev_t2 = t1, t2

        frame.alpha_composite(tracks_layer)

        # Dual glowing LED taillight streak ribbon
        if len(tail_history) >= 2:
            ribbon = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            rdraw = ImageDraw.Draw(ribbon)
            for k in range(1, len(tail_history)):
                alpha_r = int(170 * (k / len(tail_history)) ** 1.6)
                rdraw.line([tail_history[k - 1][0], tail_history[k][0]], fill=(244, 63, 94, alpha_r), width=2 * S)
                rdraw.line([tail_history[k - 1][1], tail_history[k][1]], fill=(244, 63, 94, alpha_r), width=2 * S)
            ribbon = ribbon.filter(ImageFilter.GaussianBlur(radius=1.2 * S))
            frame.alpha_composite(ribbon)

        # Smoke particles
        if smoke_particles:
            smoke_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(smoke_layer)
            live_smoke = []
            for p in smoke_particles:
                p[0] += p[2]
                p[1] += p[3]
                p[4] += 0.45 * S
                p[5] += 1
                if p[5] < p[6]:
                    live_smoke.append(p)
                    al = int(48 * (1.0 - p[5] / float(p[6])))
                    rr = p[4]
                    sdraw.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=(186, 210, 235, al))
            smoke_particles = live_smoke
            smoke_layer = smoke_layer.filter(ImageFilter.GaussianBlur(radius=3 * S))
            frame.alpha_composite(smoke_layer)

        # Volumetric soft headlight cone + neon underglow + supercar
        if -50 * S < car_x < W + 70 * S:
            # Underglow
            ug_rot = underglow_sprite.rotate(-total_angle, resample=Image.Resampling.BICUBIC, expand=True)
            uw, uh = ug_rot.size
            frame.alpha_composite(ug_rot, dest=(int(car_x - uw / 2), int(car_y - uh / 2)))

            # Headlight volumetric beam anchored at nose
            hl_rot = headlight_sprite.rotate(-total_angle, resample=Image.Resampling.BICUBIC, expand=True)
            hw, hh = hl_rot.size
            beam_cx = car_x + 95 * S * cos_a
            beam_cy = car_y + 95 * S * sin_a
            frame.alpha_composite(hl_rot, dest=(int(beam_cx - hw / 2), int(beam_cy - hh / 2)))

            # Nitro exhaust burst on final acceleration
            if f_idx >= total_frames - 24:
                flame_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                fdraw = ImageDraw.Draw(flame_layer)
                rear_x = car_x - 29 * S * cos_a
                rear_y = car_y - 29 * S * sin_a
                flen = rng.uniform(18, 30) * S
                tip_x = rear_x - flen * cos_a
                tip_y = rear_y - flen * sin_a
                fdraw.line([(rear_x, rear_y), (tip_x, tip_y)], fill=(56, 189, 248, 220), width=5 * S)
                fdraw.line([(rear_x, rear_y), (tip_x, tip_y)], fill=(255, 255, 255, 255), width=2 * S)
                frame.alpha_composite(flame_layer)

            # Rotated Car Sprite
            car_rot = car_scaled.rotate(-total_angle, resample=Image.Resampling.BICUBIC, expand=True)
            cw, ch = car_rot.size
            frame.alpha_composite(car_rot, dest=(int(car_x - cw / 2), int(car_y - ch / 2)))

        # Live HUD Footer telemetry
        ignited_cnt = len(activated_frame)
        nitro_tag = "NITRO ENGAGED" if f_idx >= total_frames - 24 else f"DRIFT {abs(slip):02.0f}°"
        draw.text((32 * S, 248 * S), f"VELOCITY: {mph} MPH // {nitro_tag}", fill=(56, 189, 248), font=font_sm)
        mid_txt = f"IGNITED NODES: {ignited_cnt:02d}/{active_days:02d} • LIVE GRID STREAM"
        mb = draw.textbbox((0, 0), mid_txt, font=font_sm)
        draw.text((W / 2 - (mb[2] - mb[0]) / 2, 248 * S), mid_txt, fill=(161, 161, 170), font=font_sm)

        # Downsample 2x -> 1x with LANCZOS for super crisp anti-aliased frame
        final_frame = frame.convert("RGB").resize((out_w, out_h), Image.Resampling.LANCZOS)
        final_frame.save(os.path.join(frames_dir, f"frame_{f_idx:03d}.png"))

    out_gif = os.path.join(assets_dir, "gta6-contribution.gif")
    palette_path = os.path.join(temp_dir, "palette.png")
    frames_pattern = os.path.join(frames_dir, "frame_%03d.png")

    subprocess.run(
        ["ffmpeg", "-y", "-framerate", "24", "-i", frames_pattern, "-vf", "palettegen=max_colors=256:stats_mode=diff", "-update", "1", palette_path],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", "24", "-i", frames_pattern, "-i", palette_path, "-lavfi", "paletteuse=dither=sierra2_4a", out_gif],
        check=True,
    )

    shutil.rmtree(temp_dir, ignore_errors=True)
    size_kb = os.path.getsize(out_gif) / 1024.0
    print(f"[generate_gta_contributions] Generated {total_frames}-frame 2x-supersampled GIF -> {out_gif} ({size_kb:.1f} KB)")
    return out_gif


if __name__ == "__main__":
    build_animation()
