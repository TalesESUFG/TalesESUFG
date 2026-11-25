#!/usr/bin/env python3
"""Generate profile-card.svg for the GitHub profile README.

Usage:
    GH_TOKEN=<token> python scripts/generate_card.py      # real data (GitHub API)
    python scripts/generate_card.py --demo                # fake data, for previewing the layout

Settings (name, subtitle, highlights, technologies...) live in profile.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"

# ---------------------------------------------------------------- theme
BG = "#0d1117"
BORDER = "#30363d"
PANEL = "#161b22"
TITLE = "#58a6ff"
TEXT = "#e6edf3"
BODY = "#c9d1d9"
MUTED = "#8b949e"
GREEN = "#2ea043"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
LEVEL_INDEX = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday contributionLevel } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes {
        isFork
        stargazerCount
        forkCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- helpers
def get_tz(name: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # no tz database (e.g. Windows without tzdata)
        return timezone(timedelta(hours=-3))


def http(url: str, token: str | None, payload: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-card-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode() if payload is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        sys.exit(f"GitHub API error {err.code} for {url}: {err.read().decode()[:300]}")


def t(x, y, text, size=12, color=BODY, weight="normal", anchor="start", extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}" {extra}>{escape(str(text))}</text>'
    )


def shade(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(c * factor))) for c in (r, g, b)))


def pts(points) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


# ---------------------------------------------------------------- data
def fetch(cfg: dict, token: str) -> dict:
    login = cfg["login"]
    tz = get_tz(cfg.get("timezone", "UTC"))
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)
    res = http(
        f"{API}/graphql",
        token,
        {"query": QUERY, "variables": {"login": login, "from": start.isoformat(), "to": now.isoformat()}},
    )
    if res.get("errors"):
        sys.exit(f"GraphQL error: {res['errors']}")
    user = res["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "weekday": d["weekday"],
         "level": LEVEL_INDEX.get(d["contributionLevel"], 0)}
        for w in cal["weeks"]
        for d in w["contributionDays"]
    ]
    originals = [r for r in user["repositories"]["nodes"] if not r["isFork"]]
    lang_size: Counter = Counter()
    lang_color: dict[str, str] = {}
    for repo in originals:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_size[name] += edge["size"]
            lang_color[name] = edge["node"]["color"] or MUTED

    events = http(f"{API}/users/{login}/events/public?per_page=100", token)
    pushes = [e for e in events if e.get("type") == "PushEvent"]
    hours = Counter(
        datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone(tz).hour for e in pushes
    )
    return {
        "name": cfg.get("display_name") or user["name"] or user["login"],
        "total": cal["totalContributions"],
        "days": days,
        "public_repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in originals),
        "forks": sum(r["forkCount"] for r in originals),
        "followers": user["followers"]["totalCount"],
        "events": len(events),
        "pushes": len(pushes),
        "hours": [hours[h] for h in range(24)],
        "languages": [(n, s, lang_color[n]) for n, s in lang_size.most_common()],
    }


def demo(cfg: dict) -> dict:
    rnd = random.Random(7)
    end = date.today()
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # align to Sunday
    days = []
    d = start
    while d <= end:
        wd = (d.weekday() + 1) % 7
        busy = 0.55 if wd in (0, 6) else 0.25
        c = 0 if rnd.random() < busy else rnd.choice([1, 1, 2, 3, 4, 6, 9])
        days.append({"date": d.isoformat(), "count": c, "weekday": wd, "level": 0})
        d += timedelta(days=1)
    mx = max(x["count"] for x in days)
    for x in days:
        x["level"] = 0 if x["count"] == 0 else min(4, 1 + int(4 * x["count"] / (mx + 1)))
    hours = [0] * 24
    for _ in range(40):
        hours[min(23, max(0, int(rnd.gauss(16, 4))))] += 1
    return {
        "name": cfg.get("display_name") or "Tales",
        "total": sum(x["count"] for x in days),
        "days": days,
        "public_repos": 8,
        "stars": 3,
        "forks": 1,
        "followers": 12,
        "events": 60,
        "pushes": 40,
        "hours": hours,
        "languages": [
            ("Python", 420000, "#3572A5"),
            ("JavaScript", 180000, "#f1e05a"),
            ("HTML", 90000, "#e34c26"),
            ("CSS", 30000, "#563d7c"),
            ("TypeScript", 20000, "#3178c6"),
            ("Shell", 5000, "#89e051"),
            ("Dockerfile", 2000, "#384d54"),
        ],
    }


# ---------------------------------------------------------------- drawing
def fmt_date(iso: str) -> str:
    return iso  # yyyy-mm-dd, matches GitHub's own format


def mini_strip(days, x, y) -> list[str]:
    """Last 16 weeks as small squares (weekly totals)."""
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)][-16:]
    totals = [sum(d["count"] for d in w) for w in weeks]
    mx = max(totals) or 1
    out = []
    for i, tot in enumerate(totals):
        lvl = 0 if tot == 0 else min(4, 1 + int(3.999 * tot / mx))
        out.append(f'<rect x="{x + i * 11}" y="{y}" width="8" height="8" rx="1.5" fill="{LEVELS[lvl]}"/>')
    return out


def iso_calendar(days, x, y, w, h) -> list[str]:
    u = (5.7, 2.6)    # one week step
    v = (-4.6, 2.6)   # one weekday step
    first = date.fromisoformat(days[0]["date"])
    offset = days[0]["weekday"]
    mx = max((d["count"] for d in days), default=0) or 1

    def P(wk, wd, z=0.0):
        return (wk * u[0] + wd * v[0], wk * u[1] + wd * v[1] - z)

    cells = []
    for d in days:
        idx = (date.fromisoformat(d["date"]) - first).days + offset
        wk, wd = divmod(idx, 7)
        cells.append((wk, wd, d))
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))

    shapes = []
    xs, ys = [], []
    for wk, wd, d in cells:
        height = 0.0 if d["count"] == 0 else 3 + 37 * (d["count"] / mx) ** 0.85
        color = LEVELS[d["level"]] if d["count"] else "#21262d"
        top = [P(wk, wd, height), P(wk + 1, wd, height), P(wk + 1, wd + 1, height), P(wk, wd + 1, height)]
        xs += [p[0] for p in top] + [P(wk, wd + 1)[0], P(wk + 1, wd)[0]]
        ys += [p[1] for p in top] + [P(wk + 1, wd + 1)[1]]
        if height:
            left = [P(wk, wd + 1), P(wk + 1, wd + 1), P(wk + 1, wd + 1, height), P(wk, wd + 1, height)]
            right = [P(wk + 1, wd), P(wk + 1, wd + 1), P(wk + 1, wd + 1, height), P(wk + 1, wd, height)]
            shapes.append(f'<polygon points="{pts(left)}" fill="{shade(color, 0.7)}"/>')
            shapes.append(f'<polygon points="{pts(right)}" fill="{shade(color, 0.5)}"/>')
            shapes.append(f'<polygon points="{pts(top)}" fill="{color}"/>')
        else:
            shapes.append(f'<polygon points="{pts(top)}" fill="{color}" stroke="{BG}" stroke-width="0.4"/>')

    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = min(w / (maxx - minx), h / (maxy - miny))
    tx = x + (w - (maxx - minx) * scale) / 2 - minx * scale
    ty = y + (h - (maxy - miny) * scale) / 2 - miny * scale
    return [f'<g transform="translate({tx:.1f},{ty:.1f}) scale({scale:.3f})">', *shapes, "</g>"]


def render(cfg: dict, data: dict) -> str:
    W = 880
    LX, LW = 28, 386
    RX, RW = 462, 390
    out: list[str] = []

    # ---------------- left column
    y = 50
    out.append(t(LX, y, data["name"], 26, TITLE, "700"))
    out.append(t(LX, y + 24, cfg.get("subtitle", ""), 12, MUTED))
    out.append(t(LX, y + 60, f'{data["total"]:,} contributions', 18, TEXT, "600"))
    days = data["days"]
    out.append(t(LX, y + 82, f'{fmt_date(days[0]["date"])} — {fmt_date(days[-1]["date"])}', 12, MUTED))
    out += mini_strip(days, LX + 225, y + 47)

    stats = [
        (f'{data["public_repos"]} public repositories', f'{data["followers"]} followers'),
        (f'{data["stars"]} star{"s" if data["stars"] != 1 else ""} · owned originals',
         f'{data["forks"]} fork{"s" if data["forks"] != 1 else ""} · owned originals'),
        (f'{data["events"]} recent public events', f'{len(data["languages"])} languages in public code'),
    ]
    sy = y + 118
    for a, b in stats:
        out.append(t(LX, sy, a, 13, BODY))
        out.append(t(LX + 225, sy, b, 13, BODY))
        sy += 26
    sy += 2
    out.append(f'<line x1="{LX}" y1="{sy}" x2="{LX + LW}" y2="{sy}" stroke="{BORDER}"/>')

    # coding activity by hour
    y = sy + 32
    out.append(t(LX, y, "Coding activity", 18, TITLE, "600"))
    out.append(t(LX, y + 22, f'Public push events by hour · {cfg.get("timezone_label", "UTC")}', 12, MUTED))
    out.append(t(LX, y + 38, f'Sample: {data["pushes"]} pushes in {data["events"]} recent public events', 11, MUTED))
    base = y + 112
    col = LW / 24
    hmax = max(data["hours"]) or 1
    for hr, c in enumerate(data["hours"]):
        cx = LX + hr * col + col / 2
        if c:
            bh = max(3, 58 * c / hmax)
            out.append(f'<rect x="{cx - 5:.1f}" y="{base - bh:.1f}" width="10" height="{bh:.1f}" rx="2" fill="{GREEN}"/>')
        else:
            out.append(f'<rect x="{cx - 5:.1f}" y="{base - 1:.1f}" width="10" height="1.5" fill="{BORDER}"/>')
        if hr % 3 == 0:
            out.append(t(cx, base + 18, f"{hr:02d}", 10, MUTED, anchor="middle"))

    # weekday
    y = base + 52
    out.append(t(LX, y, "Contributions by weekday", 12, MUTED))
    per_wd = [0] * 7
    for d in days:
        per_wd[d["weekday"]] += d["count"]
    wmax = max(per_wd) or 1
    base = y + 116
    col = LW / 7
    for i, c in enumerate(per_wd):
        cx = LX + i * col + col / 2
        bh = max(2, 80 * c / wmax) if c else 2
        out.append(f'<rect x="{cx - 9:.1f}" y="{base - bh:.1f}" width="18" height="{bh:.1f}" rx="3" fill="{GREEN}"/>')
        out.append(t(cx, base - bh - 7, c, 11, BODY, anchor="middle"))
        out.append(t(cx, base + 18, WEEKDAYS[i], 11, BODY, anchor="middle"))

    # technologies
    y = base + 60
    out.append(t(LX, y, "Languages & technologies", 18, TITLE, "600"))
    cy = y + 16
    chip_w, chip_h, gap = 88, 24, 10
    for i, tech in enumerate(cfg.get("technologies", [])):
        r, c = divmod(i, 4)
        cx = LX + c * (chip_w + gap)
        yy = cy + r * (chip_h + gap)
        out.append(f'<rect x="{cx}" y="{yy}" width="{chip_w}" height="{chip_h}" rx="4" fill="{PANEL}" stroke="{BORDER}"/>')
        out.append(t(cx + 10, yy + 16, tech, 12, BODY))
    rows = math.ceil(len(cfg.get("technologies", [])) / 4)
    y = cy + rows * (chip_h + gap) + 22
    if cfg.get("interests"):
        out.append(t(LX, y, f'Interests: {cfg["interests"]}', 12, MUTED))
    left_bottom = y

    # ---------------- right column
    y = 50
    out.append(t(RX, y, "Contributions calendar", 18, TITLE, "600"))
    out.append(t(RX, y + 22, "Public GitHub calendar · isometric view", 12, MUTED))
    out += iso_calendar(days, RX, y + 36, RW, 200)
    ly = y + 258
    out.append(t(RX, ly, "Less", 10, MUTED))
    for i, c in enumerate(LEVELS):
        out.append(f'<rect x="{RX + 30 + i * 14}" y="{ly - 9}" width="10" height="10" rx="2" fill="{c if i else "#21262d"}"/>')
    out.append(t(RX + 30 + 5 * 14 + 4, ly, "More", 10, MUTED))

    y = ly + 40
    out.append(t(RX, y, cfg.get("research_title", "Research & engineering"), 18, TITLE, "600"))
    out.append(t(RX, y + 22, cfg.get("research_org", ""), 12, MUTED))
    y += 22
    for item in cfg.get("highlights", []):
        y += 32
        out.append(t(RX + 4, y, item["title"], 13, TEXT, "600"))
        out.append(t(RX + 4, y + 19, item.get("detail", ""), 12, MUTED))
        y += 16
    if cfg.get("research_footer"):
        y += 30
        out.append(t(RX + 4, y, cfg["research_footer"], 12, MUTED))

    # languages
    y += 40
    out.append(t(RX, y, "Most used languages", 18, TITLE, "600"))
    out.append(t(RX, y + 22, "Code bytes · public owned repositories · excludes forks", 12, MUTED))
    langs = data["languages"]
    total = sum(s for _, s, _ in langs) or 1
    top = langs[:7]
    rest = sum(s for _, s, _ in langs[7:])
    if rest:
        top.append(("Other", rest, MUTED))
    by = y + 38
    out.append(f'<clipPath id="langbar"><rect x="{RX}" y="{by}" width="{RW}" height="8" rx="4"/></clipPath>')
    out.append(f'<rect x="{RX}" y="{by}" width="{RW}" height="8" rx="4" fill="{PANEL}"/>')
    out.append('<g clip-path="url(#langbar)">')
    bx = RX
    for name, size, color in top:
        seg = RW * size / total
        out.append(f'<rect x="{bx:.2f}" y="{by}" width="{seg + 0.5:.2f}" height="8" fill="{color}"/>')
        bx += seg
    out.append("</g>")
    ly = by + 34
    for i, (name, size, color) in enumerate(top):
        r, c = divmod(i, 2)
        lx = RX + c * 190
        yy = ly + r * 22
        out.append(f'<circle cx="{lx + 4}" cy="{yy - 4}" r="4" fill="{color}"/>')
        out.append(t(lx + 14, yy, f"{name} {100 * size / total:.1f}%", 12, BODY))
    y = ly + math.ceil(len(top) / 2) * 22 + 14
    out.append(t(RX, y, "Language share measures code volume, not proficiency.", 11, MUTED))
    right_bottom = y

    # ---------------- footer & frame
    fy = max(left_bottom, right_bottom) + 28
    out.append(f'<line x1="{LX}" y1="{fy}" x2="{RX + RW}" y2="{fy}" stroke="{BORDER}"/>')
    updated = datetime.now(get_tz(cfg.get("timezone", "UTC"))).strftime("%d %b %Y")
    out.append(t(LX, fy + 22, f"Updated {updated} · Public GitHub activity · Language shares by code volume", 11, MUTED))
    H = fy + 40

    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}" role="img" aria-label="{escape(data["name"])} GitHub profile card">'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
    )
    return head + "\n".join(out) + "</svg>\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="use fake data instead of the GitHub API")
    ap.add_argument("--config", default=str(ROOT / "profile.json"))
    ap.add_argument("--out", default=str(ROOT / "profile-card.svg"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.demo:
        data = demo(cfg)
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("Set GH_TOKEN (GitHub token) or run with --demo.")
        cfg["login"] = os.environ.get("GH_USER") or cfg["login"]
        data = fetch(cfg, token)
    Path(args.out).write_text(render(cfg, data), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
