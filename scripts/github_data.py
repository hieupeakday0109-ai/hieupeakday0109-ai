import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GITHUB_USERNAME", "hieupeakday0109-ai")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

LANG_COLORS = {
    "Python": "#38bdf8",
    "JavaScript": "#f59e0b",
    "TypeScript": "#3b82f6",
    "C++": "#f43f5e",
    "C#": "#a855f7",
    "Shell": "#10b981",
    "Batchfile": "#94a3b8",
    "PowerShell": "#60a5fa",
    "HTML": "#fb7185",
    "CSS": "#8b5cf6",
}

FEATURED_FALLBACK_DESC = {
    "Failure-to-Tool-Distiller": "Distills agent execution failure traces into deterministic reusable tool primitives and automated recovery guards.",
}

REPO_ORDER = [
    "Failure-to-Tool-Distiller",
    "Video-to-ASCII",
    "Scann-the-device",
    "security-check",
    "LYRIC-DISCORD",
    "key-fast-for-c-",
]


def _request_json(url: str):
    headers = {
        "User-Agent": "hieupeak-profile-builder/2.0",
        "Accept": "application/vnd.github+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def _request_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read().decode("utf-8")


def parse_contributions(username: str) -> dict:
    html = _request_text(f"https://github.com/users/{username}/contributions")
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", {"class": "ContributionCalendar-grid"})
    if not table:
        raise RuntimeError("ContributionCalendar-grid not found in GitHub contributions page.")

    # Parse exact daily counts from <tool-tip for="id">
    tooltip_counts = {}
    for tip in soup.find_all("tool-tip"):
        target_id = tip.get("for")
        if not target_id:
            continue
        txt = tip.get_text(" ", strip=True)
        m = re.match(r"^(\d+)\s+contribution", txt)
        tooltip_counts[target_id] = int(m.group(1)) if m else 0

    h2 = soup.find("h2", id="js-contribution-activity-description")
    total_from_header = None
    if h2:
        m = re.search(r"([\d,]+)\s+contribution", h2.get_text(" ", strip=True))
        if m:
            total_from_header = int(m.group(1).replace(",", ""))

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else []

    cells = []
    max_col = 0
    for r_idx, row in enumerate(rows):
        for c_idx, td in enumerate(row.find_all("td", {"class": "ContributionCalendar-day"})):
            date_str = td.get("data-date", "")
            level = int(td.get("data-level", "0"))
            td_id = td.get("id", "")
            count = tooltip_counts.get(td_id, 0)
            if level > 0 and count == 0:
                count = level
            cells.append({
                "col": c_idx,
                "row": r_idx,
                "date": date_str,
                "level": level,
                "count": count,
            })
            max_col = max(max_col, c_idx)

    # Sort chronologically by date
    valid_cells = [c for c in cells if c["date"]]
    valid_cells.sort(key=lambda c: c["date"])

    active_days = sum(1 for c in valid_cells if c["level"] > 0 or c["count"] > 0)
    total_contributions = total_from_header if total_from_header is not None else sum(c["count"] for c in valid_cells)
    max_level = max((c["level"] for c in valid_cells), default=0)
    peak_day = max(valid_cells, key=lambda c: c["count"], default={"date": "", "count": 0, "level": 0})

    # Compute streaks chronologically
    longest_streak = 0
    running = 0
    for c in valid_cells:
        if c["count"] > 0 or c["level"] > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    # Current streak: trailing days ending at today or yesterday
    current_streak = 0
    if valid_cells:
        idx = len(valid_cells) - 1
        # If today has 0 commits yet, allow starting from yesterday if yesterday had > 0
        if valid_cells[idx]["count"] == 0 and valid_cells[idx]["level"] == 0 and idx > 0:
            idx -= 1
        while idx >= 0 and (valid_cells[idx]["count"] > 0 or valid_cells[idx]["level"] > 0):
            current_streak += 1
            idx -= 1

    # Weekly buckets (columns 0..max_col)
    num_cols = max_col + 1
    weekly = [0] * num_cols
    for c in valid_cells:
        weekly[c["col"]] += c["count"]

    # Day-of-week distribution: GitHub grid rows are 0=Sun .. 6=Sat
    dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow_counts = [0] * 7
    for c in valid_cells:
        dow_counts[c["row"] % 7] += c["count"]
    # Reorder Mon..Sun for cleaner engineering display
    weekday_order = [1, 2, 3, 4, 5, 6, 0]
    weekday_distribution = [
        {"day": dow_names[i], "count": dow_counts[i]} for i in weekday_order
    ]

    # Parse month labels
    months = []
    thead = table.find("thead")
    curr_col = 0
    if thead:
        for td in thead.find_all("td", {"class": "ContributionCalendar-label"}):
            span = td.find("span", {"aria-hidden": "true"})
            colspan = int(td.get("colspan", "1"))
            if span and span.get_text(strip=True):
                months.append({"col": curr_col, "label": span.get_text(strip=True)})
            curr_col += colspan

    return {
        "total_contributions": total_contributions,
        "active_days": active_days,
        "max_level": max_level,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "peak_day": peak_day,
        "num_cols": num_cols,
        "months": months,
        "weekly_counts": weekly,
        "weekday_distribution": weekday_distribution,
        "cells": valid_cells,
    }


def fetch_profile_and_repos(username: str) -> dict:
    user = _request_json(f"https://api.github.com/users/{username}")
    repos_raw = _request_json(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=50")

    lang_totals = {}
    repos_clean = []
    total_stars = 0
    total_forks = 0

    for r in repos_raw:
        if r.get("fork"):
            continue
        total_stars += r.get("stargazers_count", 0)
        total_forks += r.get("forks_count", 0)

        langs = {}
        try:
            langs = _request_json(r["languages_url"])
        except Exception:
            if r.get("language"):
                langs = {r["language"]: max(1000, r.get("size", 1) * 100)}

        for lang_name, byte_cnt in langs.items():
            lang_totals[lang_name] = lang_totals.get(lang_name, 0) + byte_cnt

        desc = (r.get("description") or "").strip()
        if not desc:
            desc = FEATURED_FALLBACK_DESC.get(r["name"], "Engineering system & architectural tooling repository.")

        primary_lang = r.get("language") or (max(langs, key=langs.get) if langs else "Markdown")
        repos_clean.append({
            "name": r["name"],
            "description": desc,
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "language": primary_lang,
            "language_color": LANG_COLORS.get(primary_lang, "#94a3b8"),
            "html_url": r["html_url"],
            "updated_at": r.get("updated_at", ""),
            "size_kb": r.get("size", 0),
        })

    # Order featured repos cleanly (exclude profile repo itself from showcase cards)
    showcase = [r for r in repos_clean if r["name"].lower() != username.lower()]
    order_map = {name: i for i, name in enumerate(REPO_ORDER)}
    showcase.sort(key=lambda r: (order_map.get(r["name"], 99), -r["stars"], r["name"].lower()))

    total_lang_bytes = sum(lang_totals.values()) or 1
    languages = []
    for name, b in sorted(lang_totals.items(), key=lambda kv: -kv[1]):
        pct = round((b / total_lang_bytes) * 100.0, 2)
        if pct >= 0.1:
            languages.append({
                "name": name,
                "bytes": b,
                "percent": pct,
                "color": LANG_COLORS.get(name, "#94a3b8"),
            })

    return {
        "user": {
            "login": user.get("login", username),
            "public_repos": user.get("public_repos", len(repos_clean)),
            "followers": user.get("followers", 0),
            "following": user.get("following", 0),
            "created_at": user.get("created_at", ""),
            "total_stars": total_stars,
            "total_forks": total_forks,
        },
        "languages": languages[:6],
        "featured_repos": showcase[:6],
        "all_repos": repos_clean,
    }


def collect_and_save(repo_root: str) -> dict:
    assets_dir = os.path.join(repo_root, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    out_path = os.path.join(assets_dir, "profile-data.json")

    tz_vn = timezone(timedelta(hours=7))
    now_str = datetime.now(tz_vn).strftime("%Y-%m-%d %H:%M UTC+7")

    try:
        contrib = parse_contributions(USERNAME)
        gh = fetch_profile_and_repos(USERNAME)
        data = {
            "schema_version": 2,
            "username": USERNAME,
            "synced_at": now_str,
            "user": gh["user"],
            "contributions": contrib,
            "languages": gh["languages"],
            "featured_repos": gh["featured_repos"],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[github_data] Synced live data -> {out_path} ({contrib['total_contributions']} contribs, {contrib['active_days']} active days)")
        return data
    except Exception as exc:
        if os.path.exists(out_path):
            print(f"[github_data] Warning: live fetch failed ({exc}), using cached {out_path}")
            with open(out_path, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = collect_and_save(root)
    print("Languages:", [(l["name"], l["percent"]) for l in d["languages"]])
    print("Featured:", [r["name"] for r in d["featured_repos"]])
