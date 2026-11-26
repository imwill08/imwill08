#!/usr/bin/env python3
"""Generates cards/heatmap.svg and cards/activity.svg from your real GitHub contributions.
Usage: GITHUB_TOKEN=... python scripts/generate_cards.py --user imwill08
       python scripts/generate_cards.py --demo     (fake data, for a local preview only)
"""
import argparse, json, os, random, urllib.request
from collections import OrderedDict
from datetime import date, timedelta

BG, INK, MUTED, BLUE, GREY = "#f2f2f0", "#111111", "#6b6b66", "#2f4bff", "#c9c9c4"
SERIF = "'Instrument Serif','Playfair Display',Georgia,'Times New Roman',serif"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
LEVELS = ["#dedee2", "#c3cdff", "#8fa3ff", "#4a67ff", "#1f35d8"]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""

def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        cal = json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], [w["contributionDays"] for w in cal["weeks"]]

def demo():
    random.seed(7)
    start = date.today() - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    weeks, d = [], start
    while d <= date.today():
        wk = []
        for i in range(7):
            n = 0 if (d > date.today() or random.random() < 0.3) else random.choice([1, 2, 3, 5, 8, 13, 21])
            wk.append({"date": d.isoformat(), "contributionCount": n, "weekday": i})
            d += timedelta(days=1)
        weeks.append(wk)
    return sum(x["contributionCount"] for w in weeks for x in w), weeks

def level(n, cuts):
    if n == 0: return 0
    return 1 + sum(n > c for c in cuts)

def heatmap_svg(weeks):
    counts = sorted(x["contributionCount"] for w in weeks for x in w if x["contributionCount"] > 0)
    q = lambda f: counts[int(len(counts) * f)] if counts else 1
    cuts = [q(0.25), q(0.5), q(0.75)]
    cell, gap, x0, y0 = 12, 3, 40, 100
    out, last_x = [], -99
    for c, wk in enumerate(weeks):
        x = x0 + c * (cell + gap)
        for day in wk:
            if day["date"] > date.today().isoformat(): continue
            y = y0 + day["weekday"] * (cell + gap)
            col = LEVELS[level(day["contributionCount"], cuts)]
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{col}"/>')
        m = int(wk[0]["date"][5:7]) - 1
        if (c == 0 or int(weeks[c-1][0]["date"][5:7]) - 1 != m) and x - last_x >= 44:
            out.append(f'<text x="{x}" y="{y0 + 7*(cell+gap) + 18}" font-family="{MONO}" font-size="11" fill="{MUTED}">{MONTHS[m]}</text>')
            last_x = x
    lx = 900 - 40 - 5 * 15 - 60
    out.append(f'<text x="{lx}" y="{y0 + 7*(cell+gap) + 18}" font-family="{MONO}" font-size="11" fill="{MUTED}" text-anchor="end">less</text>')
    for i, col in enumerate(LEVELS):
        out.append(f'<rect x="{lx + 8 + i*15}" y="{y0 + 7*(cell+gap) + 8}" width="12" height="12" rx="2" fill="{col}"/>')
    out.append(f'<text x="{lx + 8 + 5*15 + 4}" y="{y0 + 7*(cell+gap) + 18}" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text>')
    H = y0 + 7 * (cell + gap) + 36
    return (f'<svg width="900" height="{H}" viewBox="0 0 900 {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Contribution heatmap, refreshed daily">'
            f'<rect width="900" height="{H}" rx="20" fill="{BG}"/>'
            f'<text x="40" y="62" font-family="{SERIF}" font-size="38" fill="{INK}">Every day, <tspan font-style="italic" fill="{BLUE}">in blue</tspan></text>'
            f'<text x="860" y="58" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2" fill="{MUTED}">REFRESHED DAILY</text>'
            + "".join(out) + "</svg>")

def streaks(days):
    days = [d for d in days if d["date"] <= date.today().isoformat()]
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, cur)
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i]["contributionCount"] == 0: i -= 1
    while i >= 0 and days[i]["contributionCount"] > 0:
        cur += 1; i -= 1
    return cur, longest

def activity_svg(total, weeks):
    days = [x for w in weeks for x in w if x["date"] <= date.today().isoformat()]
    months = OrderedDict()
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["contributionCount"]
    keys = list(months)[-12:]
    vals = [months[k] for k in keys]
    peak = max(vals) if vals else 1
    cur, longest = streaks(days)
    active = sum(1 for d in days if d["contributionCount"] > 0)
    busiest = max((d["contributionCount"] for d in days), default=0)
    bars, base, maxh, bw, pitch = [], 292, 120, 32, 44
    for i, (k, v) in enumerate(zip(keys, vals)):
        h = max(4, round(maxh * v / peak)) if peak else 4
        x = 40 + i * pitch
        col = BLUE if v == peak else (GREY if i == len(keys) - 1 else INK)
        bars.append(f'<rect x="{x}" y="{base-h}" width="{bw}" height="{h}" rx="2" fill="{col}"/>')
        if v == peak:
            bars.append(f'<text x="{x + bw/2}" y="{base-h-8}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{BLUE}">{v:,}</text>')
        bars.append(f'<text x="{x + bw/2}" y="{base+20}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUTED}">{MONTHS[int(k[5:7])-1]}</text>')
    def stat(y, big, unit, sub):
        return (f'<text x="640" y="{y}" font-family="{SERIF}" font-size="42" fill="{INK}">{big}<tspan font-style="italic" fill="{INK}">{unit}</tspan></text>'
                f'<text x="640" y="{y+22}" font-family="{SANS}" font-size="13" fill="{MUTED}">{sub}</text>')
    H = 340
    return (f'<svg width="900" height="{H}" viewBox="0 0 900 {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{total} contributions in the last 12 months">'
            f'<rect width="900" height="{H}" rx="20" fill="{BG}"/>'
            f'<text x="40" y="56" font-family="{MONO}" font-size="12" letter-spacing="2" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>'
            f'<text x="40" y="122" font-family="{SERIF}" font-size="64" fill="{INK}">{total:,} <tspan font-style="italic">contributions</tspan></text>'
            + "".join(bars) +
            stat(104, f"{cur} ", "days", f"current streak · longest {longest}") +
            f'<line x1="640" y1="150" x2="860" y2="150" stroke="#dcdcd6"/>' +
            stat(196, f"{active}", f" / {len(days)}", "days with a commit") +
            f'<line x1="640" y1="242" x2="860" y2="242" stroke="#dcdcd6"/>' +
            stat(288, f"{busiest}", "", "on the busiest day") + "</svg>")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GH_USER", "imwill08"))
    ap.add_argument("--out", default="cards")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    total, weeks = demo() if a.demo else fetch(a.user, os.environ["GITHUB_TOKEN"])
    os.makedirs(a.out, exist_ok=True)
    open(f"{a.out}/heatmap.svg", "w").write(heatmap_svg(weeks))
    open(f"{a.out}/activity.svg", "w").write(activity_svg(total, weeks))
    print("wrote", a.out)
