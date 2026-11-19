import math
import os
import sys
import urllib.request
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GITHUB_USERNAME", "hieupeakday0109-ai")

def fetch_contributions(username):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.read().decode("utf-8")

def build_animation():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    assets_dir = os.path.join(repo_root, "assets")
    temp_dir = os.path.join(repo_root, ".gta_temp")
    frames_dir = os.path.join(temp_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    print(f"Fetching live contributions for @{USERNAME}...")
    html_content = fetch_contributions(USERNAME)
    soup = BeautifulSoup(html_content, "html.parser")

    table = soup.find("table", {"class": "ContributionCalendar-grid"})
    if not table:
        print("Error: Could not find ContributionCalendar-grid in HTML!")
        sys.exit(1)

    rows = table.find("tbody").find_all("tr")

    grid = {}
    total_commits = 0
    max_level = 0
    for r_idx, row in enumerate(rows):
        cells = row.find_all("td", {"class": "ContributionCalendar-day"})
        for c_idx, cell in enumerate(cells):
            date = cell.get("data-date", "")
            level = int(cell.get("data-level", "0"))
            grid[(c_idx, r_idx)] = {"date": date, "level": level}
            if level > 0:
                total_commits += 1
                max_level = max(max_level, level)

    # Months
    thead = table.find("thead")
    months = []
    curr_col = 0
    if thead:
        for td in thead.find_all("td", {"class": "ContributionCalendar-label"}):
            txt = td.find("span", {"aria-hidden": "true"})
            colspan = int(td.get("colspan", "1"))
            if txt and txt.get_text(strip=True):
                months.append((curr_col, txt.get_text(strip=True)))
            curr_col += colspan

    # Setup Canvas
    width, height = 880, 260
    grid_x0 = 68
    grid_y0 = 84
    cell_w, cell_h = 11, 11
    gap = 3
    pitch = cell_w + gap

    # Fonts fallback
    def get_font(size, is_bold=False):
        font_paths = [
            r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
        for p in font_paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_mono_sm = get_font(10)
    font_mono_md = get_font(12)
    font_sans_lg = get_font(14, is_bold=True)

    # Car sprite
    car_path = os.path.join(assets_dir, "car_sprite.png")
    if not os.path.exists(car_path):
        car_path = os.path.join(repo_root, "car_transparent.png")
    
    car_src = Image.open(car_path).convert("RGBA")
    car_scaled = car_src.resize((56, 23), Image.Resampling.LANCZOS)

    bg_color = (13, 15, 23)
    cell_empty = (21, 24, 36)
    cell_border = (30, 34, 53)

    color_levels = {
        1: (139, 92, 246),  # Violet #8b5cf6
        2: (236, 72, 153),  # Hot Pink #ec4899
        3: (244, 63, 94),   # Coral #f43f5e
        4: (251, 191, 36),  # Amber Sunburst #fbbf24
    }

    total_frames = 135

    def get_rc_center(c, r):
        return grid_x0 + c * pitch + cell_w / 2, grid_y0 + r * pitch + cell_h / 2

    # Waypoints based on active commits
    p_c17 = get_rc_center(17, 4)
    p_c40 = get_rc_center(40, 3.5)
    p_c43_l4 = get_rc_center(43, 3)
    p_c43_b = get_rc_center(43, 6)
    p_c45_t = get_rc_center(45, 0)
    p_c47 = get_rc_center(47, 1.5)
    p_c52 = get_rc_center(52, 4)

    waypoints = [
        (0, -70, get_rc_center(0, 3)[1], 0),
        (22, get_rc_center(10, 3)[0], get_rc_center(10, 3)[1], 0),
        (36, p_c17[0] - 25, p_c17[1] - 8, 12),
        (44, p_c17[0] + 12, p_c17[1], 4),
        (66, p_c40[0] - 40, p_c40[1] - 5, 0),
        (76, p_c40[0], p_c40[1], 8),
        (85, p_c43_b[0] - 10, p_c43_b[1], -22),
        (94, p_c43_l4[0], p_c43_l4[1], 28),
        (102, p_c45_t[0], p_c45_t[1] - 5, -18),
        (110, p_c47[0], p_c47[1], 12),
        (118, p_c52[0], p_c52[1], 0),
        (128, width + 70, p_c52[1], 0),
        (135, width + 90, p_c52[1], 0),
    ]

    def interpolate_path(wp, total_f):
        times = [w[0] for w in wp]
        xs = [w[1] for w in wp]
        ys = [w[2] for w in wp]
        drifts = [w[3] for w in wp]
        path = []
        for f in range(total_f):
            idx = 0
            while idx < len(times) - 2 and times[idx+1] <= f:
                idx += 1
            t0, t1 = times[idx], times[idx+1]
            alpha = (f - t0) / float(t1 - t0) if t1 > t0 else 0
            alpha_s = alpha * alpha * (3 - 2 * alpha)
            x = xs[idx] + (xs[idx+1] - xs[idx]) * alpha_s
            y = ys[idx] + (ys[idx+1] - ys[idx]) * alpha_s
            drift = drifts[idx] + (drifts[idx+1] - drifts[idx]) * alpha_s
            path.append((x, y, drift))
        return path

    path = interpolate_path(waypoints, total_frames)

    tracks_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    tracks_draw = ImageDraw.Draw(tracks_layer)

    activated_frame = {}
    smoke_particles = []
    prev_t1, prev_t2 = None, None

    for f_idx in range(total_frames):
        frame = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(frame)

        for gy in range(0, height, 20):
            draw.line([(0, gy), (width, gy)], fill=(17, 20, 30, 80), width=1)
        for gx in range(0, width, 20):
            draw.line([(gx, 0), (gx, height)], fill=(17, 20, 30, 80), width=1)

        draw.text((grid_x0, 18), f"GT-01 // @{USERNAME} • CONTRIBUTION HIGHWAY", fill=(241, 245, 249), font=font_sans_lg)
        draw.text((width - grid_x0 - 230, 20), f"PEAK: LEVEL {max_level} • {total_commits} ACTIVE DAYS", fill=(148, 163, 184), font=font_mono_md)
        draw.line([(grid_x0, 48), (width - grid_x0, 48)], fill=(39, 39, 42), width=1)

        for col_idx, m_name in months:
            mx = grid_x0 + col_idx * pitch
            draw.text((mx, 62), m_name, fill=(113, 113, 122), font=font_mono_sm)

        day_labels = {1: "Mon", 3: "Wed", 5: "Fri"}
        for r_idx, d_name in day_labels.items():
            dy = grid_y0 + r_idx * pitch - 1
            draw.text((grid_x0 - 32, dy), d_name, fill=(82, 82, 91), font=font_mono_sm)

        car_x, car_y, car_drift = path[f_idx]
        if f_idx < total_frames - 1:
            next_x, next_y, _ = path[f_idx + 1]
            dx = next_x - car_x
            dy = next_y - car_y
        else:
            dx, dy = 1.0, 0.0

        move_angle = math.degrees(math.atan2(dy, dx))
        total_angle = move_angle + car_drift
        rad = math.radians(total_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        for (c, r), cdata in grid.items():
            cx = grid_x0 + c * pitch + cell_w / 2
            cy = grid_y0 + r * pitch + cell_h / 2
            if car_x >= cx - 18 and cdata["level"] > 0:
                if (c, r) not in activated_frame:
                    activated_frame[(c, r)] = f_idx

        for (c, r), cdata in grid.items():
            x1 = grid_x0 + c * pitch
            y1 = grid_y0 + r * pitch
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            lvl = cdata["level"]
            if (c, r) in activated_frame:
                act_age = f_idx - activated_frame[(c, r)]
                base_col = color_levels.get(lvl, (139, 92, 246))
                if act_age < 3:
                    cell_col = (255, 255, 255)
                    draw.rounded_rectangle([x1 - 3, y1 - 3, x2 + 3, y2 + 3], radius=4, fill=(base_col[0], base_col[1], base_col[2], 90))
                else:
                    if lvl == 4:
                        pulse = int(18 * math.sin(f_idx * 0.35))
                        cell_col = (min(255, base_col[0] + pulse), min(255, base_col[1] + pulse), base_col[2])
                        draw.rounded_rectangle([x1 - 2, y1 - 2, x2 + 2, y2 + 2], radius=3, fill=(base_col[0], base_col[1], base_col[2], 75))
                    else:
                        cell_col = base_col
                draw.rounded_rectangle([x1, y1, x2, y2], radius=2, fill=cell_col)
            else:
                draw.rounded_rectangle([x1, y1, x2, y2], radius=2, fill=cell_empty, outline=cell_border, width=1)

        if -40 < car_x < width + 40:
            t1 = (car_x - 18 * cos_a - 9 * sin_a, car_y - 18 * sin_a + 9 * cos_a)
            t2 = (car_x - 18 * cos_a + 9 * sin_a, car_y - 18 * sin_a - 9 * cos_a)
            if abs(car_drift) > 4:
                if prev_t1 and prev_t2:
                    tracks_draw.line([prev_t1, t1], fill=(5, 5, 9, 90), width=2)
                    tracks_draw.line([prev_t2, t2], fill=(5, 5, 9, 90), width=2)
                if f_idx % 2 == 0:
                    smoke_particles.append([t1[0], t1[1], -cos_a * 1.2 + np.random.uniform(-0.4, 0.4), -sin_a * 1.2 + np.random.uniform(-0.4, 0.4), 2.5, 0, 15])
                    smoke_particles.append([t2[0], t2[1], -cos_a * 1.2 + np.random.uniform(-0.4, 0.4), -sin_a * 1.2 + np.random.uniform(-0.4, 0.4), 2.5, 0, 15])
            prev_t1, prev_t2 = t1, t2
        else:
            prev_t1, prev_t2 = None, None

        frame.alpha_composite(tracks_layer)

        if smoke_particles:
            smoke_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            smoke_draw = ImageDraw.Draw(smoke_layer)
            live_smoke = []
            for s in smoke_particles:
                s[0] += s[2]
                s[1] += s[3]
                s[4] += 0.35
                s[5] += 1
                alpha = int(45 * (1.0 - s[5] / float(s[6])))
                if s[5] < s[6]:
                    live_smoke.append(s)
                    r = s[4]
                    smoke_draw.ellipse([s[0] - r, s[1] - r, s[0] + r, s[1] + r], fill=(210, 220, 235, alpha))
            smoke_particles = live_smoke
            smoke_layer = smoke_layer.filter(ImageFilter.GaussianBlur(radius=3))
            frame.alpha_composite(smoke_layer)

        if -40 < car_x < width + 60:
            cone_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            cone_draw = ImageDraw.Draw(cone_layer)
            front_x = car_x + 24 * cos_a
            front_y = car_y + 24 * sin_a
            beam_len = 145
            spread = 42
            p_left = (front_x + beam_len * cos_a - spread * (-sin_a), front_y + beam_len * sin_a - spread * cos_a)
            p_right = (front_x + beam_len * cos_a + spread * (-sin_a), front_y + beam_len * sin_a + spread * cos_a)
            cone_draw.polygon([(front_x, front_y), p_left, p_right], fill=(255, 255, 255, 28))
            cone_layer = cone_layer.filter(ImageFilter.GaussianBlur(radius=5))
            frame.alpha_composite(cone_layer)

        if 116 <= f_idx <= 130 and -40 < car_x < width + 50:
            flame_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            flame_draw = ImageDraw.Draw(flame_layer)
            rear_x = car_x - 27 * cos_a
            rear_y = car_y - 27 * sin_a
            flame_len = np.random.uniform(16, 26)
            tip_x = rear_x - flame_len * cos_a
            tip_y = rear_y - flame_len * sin_a
            flame_draw.line([(rear_x, rear_y), (tip_x, tip_y)], fill=(56, 189, 248, 220), width=4)
            flame_draw.line([(rear_x, rear_y), (tip_x, tip_y)], fill=(255, 255, 255, 255), width=2)
            frame.alpha_composite(flame_layer)

        if -60 < car_x < width + 70:
            car_rotated = car_scaled.rotate(-total_angle, resample=Image.Resampling.BICUBIC, expand=True)
            cw, ch = car_rotated.size
            car_pos = (int(car_x - cw / 2), int(car_y - ch / 2))
            frame.alpha_composite(car_rotated, dest=car_pos)

        draw.line([(grid_x0, 225), (width - grid_x0, 225)], fill=(30, 34, 53), width=1)
        draw.text((grid_x0, 235), "SPEED: 195 MPH // NITRO: DUAL STAGE", fill=(100, 116, 139), font=font_mono_sm)
        draw.text((width / 2 - 80, 235), "VICE CITY GRID // REAL-TIME REPO STREAM", fill=(148, 163, 184), font=font_mono_sm)
        
        leg_x = width - grid_x0 - 145
        draw.text((leg_x, 235), "Less", fill=(100, 116, 139), font=font_mono_sm)
        leg_x += 28
        draw.rounded_rectangle([leg_x, 235, leg_x + 9, 244], radius=2, fill=cell_empty, outline=cell_border)
        leg_x += 12
        for lvl in [1, 2, 3, 4]:
            draw.rounded_rectangle([leg_x, 235, leg_x + 9, 244], radius=2, fill=color_levels[lvl])
            leg_x += 12
        draw.text((leg_x + 2, 235), "More", fill=(100, 116, 139), font=font_mono_sm)

        frame_rgb = frame.convert("RGB")
        frame_rgb.save(os.path.join(frames_dir, f"frame_{f_idx:03d}.png"))

    print(f"Generated {total_frames} frames.")

    # Compile with ffmpeg
    out_gif = os.path.join(assets_dir, "gta6-contribution.gif")
    palette_path = os.path.join(temp_dir, "palette.png")

    frames_pattern = os.path.join(frames_dir, "frame_%03d.png")
    subprocess.run(["ffmpeg", "-y", "-framerate", "22", "-i", frames_pattern, "-vf", "palettegen=stats_mode=diff", palette_path], check=True)
    subprocess.run(["ffmpeg", "-y", "-framerate", "22", "-i", frames_pattern, "-i", palette_path, "-lavfi", "paletteuse=dither=bayer:bayer_scale=3", out_gif], check=True)

    print(f"Success! Output generated at: {out_gif}")

if __name__ == "__main__":
    build_animation()
