#!/usr/bin/env python3
"""Generate profile README assets (banner, contribution heatmap, stats card)
from the GitHub API. Stdlib-only so it runs in GitHub Actions too.

Usage:  python3 scripts/generate_assets.py [--user sajxraj] [--out assets]
Requires `gh` authenticated (GITHUB_TOKEN / GH_TOKEN in CI).
"""
import argparse, base64, datetime, json, subprocess, sys, urllib.request
from pathlib import Path

# ---------- palette (single source of visual truth) ----------
BG       = "#0d1117"
BG_SOFT  = "#161b22"
BORDER   = "#30363d"
TEXT     = "#e6edf3"
TEXT_DIM = "#8b949e"
ACCENT   = "#39d353"   # github green
ACCENT2  = "#58a6ff"   # github blue
ACCENT3  = "#bc8cff"   # github purple
LEVELS   = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FONT     = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO     = "'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',monospace"


def gh(*args):
    args = list(args)
    while len(args) > 1 and not str(args[1]).startswith("-"):
        args = [f"{args[0]}/{args[1]}"] + args[2:]
    r = subprocess.run(["gh", "api"] + [str(a) for a in args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gh api {' '.join(map(str,args))} failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def svg_doc(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" fill="none">\n{body}\n</svg>\n')


def card(w, h):
    return (f'<rect width="{w}" height="{h}" rx="14" fill="{BG}" '
            f'stroke="{BORDER}"/>')


# ---------- data ----------
def fetch_data(user):
    u = gh("users", user)
    repos = gh(f"users/{user}/repos?per_page=100")
    public = [r for r in repos if not r.get("fork") and not r.get("private")]
    stars = sum(r["stargazers_count"] for r in public)
    prs = gh(f"search/issues?q=author:{user}+type:pr")["total_count"]
    cal = gh("graphql", "-f",
             'query={user(login:"%s"){contributionsCollection{contributionCalendar'
             '{totalContributions weeks{contributionDays{date contributionCount}}}}}}' % user
             )["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return {
        "user": user, "name": u.get("name") or user,
        "avatar_url": u["avatar_url"],
        "followers": u["followers"], "repos": len(public), "stars": stars,
        "prs": prs, "calendar": cal,
    }


# ---------- banner ----------
def banner_svg(d, avatar_b64):
    W, H = 1000, 210
    chips = ["Laravel", "Inertia", "Vue", "TypeScript", "Node", "AI tooling"]
    parts = [card(W, H)]
    # dotted texture, right half only
    parts.append(f'<g opacity="0.35">')
    for x in range(560, W - 12, 22):
        for y in range(20, H - 12, 22):
            parts.append(f'<circle cx="{x}" cy="{y}" r="1.4" fill="{BORDER}"/>')
    parts.append("</g>")
    # avatar
    parts.append(
        f'<clipPath id="av"><circle cx="106" cy="105" r="58"/></clipPath>'
        f'<image href="data:image/png;base64,{avatar_b64}" x="48" y="47" width="116" height="116" clip-path="url(#av)"/>'
        f'<circle cx="106" cy="105" r="58" stroke="{BORDER}" stroke-width="1.5" fill="none"/>'
        f'<circle cx="148" cy="146" r="7" fill="{ACCENT}" stroke="{BG}" stroke-width="3"/>')
    # name + subtitle
    parts.append(f'<text x="200" y="88" font-family="{FONT}" font-size="34" '
                 f'font-weight="700" fill="{TEXT}">{esc(d["name"])}</text>')
    parts.append(f'<text x="200" y="118" font-family="{FONT}" font-size="15.5" '
                 f'fill="{TEXT_DIM}">Senior Software Engineer · Kathmandu, Nepal · '
                 f'<tspan fill="{ACCENT}">@{esc(d["user"])}</tspan></text>')
    # chips
    x = 200
    for c in chips:
        w = 26 + 8.6 * len(c)
        parts.append(f'<rect x="{x}" y="142" width="{w}" height="27" rx="13.5" '
                     f'fill="{BG_SOFT}" stroke="{BORDER}"/>'
                     f'<text x="{x + w/2}" y="160" text-anchor="middle" '
                     f'font-family="{FONT}" font-size="12.5" fill="{TEXT_DIM}">{esc(c)}</text>')
        x += w + 8
    return svg_doc(W, H, "\n".join(parts))


# ---------- heatmap ----------
def heatmap_body(d):
    cell, gap = 10, 2
    left, top, pad = 40, 58, 18
    weeks = d["calendar"]["weeks"]
    days = [dd for w in weeks for dd in w["contributionDays"]]
    cols = len(weeks)
    W = pad + left + cols * (cell + gap) + pad
    H = pad + top + 7 * (cell + gap) + 30
    parts = []
    parts.append(f'<text x="{pad+14}" y="30" font-family="{FONT}" font-size="14.5" '
                 f'font-weight="600" fill="{TEXT}">{d["calendar"]["totalContributions"]:,} '
                 f'contributions in the last year</text>')
    maxc = max((dd["contributionCount"] for dd in days), default=1) or 1
    # month labels
    seen = set()
    for i, w in enumerate(weeks):
        first = w["contributionDays"][0]
        m = datetime.date.fromisoformat(first["date"]).strftime("%b")
        if m not in seen and i < cols - 1:
            seen.add(m)
            parts.append(f'<text x="{pad+left+i*(cell+gap)}" y="{top-8}" '
                         f'font-family="{FONT}" font-size="10" fill="{TEXT_DIM}">{m}</text>')
    for r, wd in enumerate(["", "Mon", "", "Wed", "", "Fri", ""]):
        if wd:
            parts.append(f'<text x="{pad+6}" y="{top+r*(cell+gap)+cell-1}" '
                         f'font-family="{FONT}" font-size="10" fill="{TEXT_DIM}">{wd}</text>')
    for i, w in enumerate(weeks):
        for dd in w["contributionDays"]:
            r = datetime.date.fromisoformat(dd["date"]).weekday()
            c = dd["contributionCount"]
            lvl = 0 if c == 0 else min(4, int(1 + 3.99 * (c / maxc) ** 0.55))
            parts.append(f'<rect x="{pad+left+i*(cell+gap):.1f}" '
                         f'y="{top+r*(cell+gap):.1f}" width="{cell}" height="{cell}" '
                         f'rx="2.5" fill="{LEVELS[lvl]}"/>')
    # legend
    ly = H - pad - 10
    lx = W - pad - 5 * (cell + gap) - 78
    parts.append(f'<text x="{lx-52}" y="{ly+9}" font-family="{FONT}" font-size="10" '
                 f'fill="{TEXT_DIM}">Less</text>')
    for i in range(5):
        parts.append(f'<rect x="{lx+i*(cell+gap):.1f}" y="{ly}" width="{cell}" '
                     f'height="{cell}" rx="2.5" fill="{LEVELS[i]}"/>')
    parts.append(f'<text x="{lx+5*(cell+gap)+5:.1f}" y="{ly+9}" font-family="{FONT}" '
                 f'font-size="10" fill="{TEXT_DIM}">More</text>')
    return parts, W, H


# ---------- stats card ----------
def stats_body(d):
    W, H = 300, 316
    parts = []
    parts.append(f'<text x="20" y="34" font-family="{FONT}" font-size="14.5" '
                 f'font-weight="600" fill="{TEXT}">On GitHub</text>')
    stats = [("Stars earned", d["stars"], ACCENT),
             ("Public repos", d["repos"], ACCENT2),
             ("Merged PRs", d["prs"], ACCENT3),
             ("Followers", d["followers"], "#f778ba")]
    for i, (label, val, color) in enumerate(stats):
        y = 68 + i * 32
        parts.append(f'<text x="20" y="{y}" font-family="{FONT}" font-size="13" '
                     f'fill="{TEXT_DIM}">{label}</text>')
        parts.append(f'<text x="{W-20}" y="{y}" text-anchor="end" '
                     f'font-family="{MONO}" font-size="15" font-weight="700" '
                     f'fill="{color}">{val:,}</text>')
    # languages: one row each — dot, name, right-aligned pct, bar
    y0 = 68 + 4 * 32 + 8
    parts.append(f'<text x="20" y="{y0}" font-family="{FONT}" font-size="13" '
                 f'fill="{TEXT_DIM}">Top languages</text>')
    total = sum(v for _, v in d["langs"]) or 1
    for i, (name, v) in enumerate(d["langs"]):
        color = [ACCENT, ACCENT2, ACCENT3, "#f778ba", "#d2a8ff"][i]
        pct = v / total
        y = y0 + 26 + i * 30
        parts.append(f'<circle cx="24" cy="{y-4}" r="3.5" fill="{color}"/>')
        parts.append(f'<text x="34" y="{y}" font-family="{FONT}" font-size="12" '
                     f'fill="{TEXT}">{esc(name)}</text>')
        parts.append(f'<text x="{W-20}" y="{y}" text-anchor="end" '
                     f'font-family="{MONO}" font-size="12" fill="{TEXT_DIM}">'
                     f'{pct*100:.0f}%</text>')
        parts.append(f'<rect x="20" y="{y+7}" width="{W-40}" height="4" rx="2" '
                     f'fill="{BG_SOFT}"/>')
        parts.append(f'<rect x="20" y="{y+7}" width="{max(4,(W-40)*pct):.0f}" '
                     f'height="4" rx="2" fill="{color}"/>')
    return parts, W, H


# ---------- separate stacked cards ----------
def heatmap_card(d):
    parts, W, H = heatmap_body(d)
    return svg_doc(W, H, "\n".join([card(W, H)] + parts))


def stats_card(d, W=712):
    H = 130
    parts = [card(W, H)]
    parts.append(f'<text x="20" y="34" font-family="{FONT}" font-size="14.5" '
                 f'font-weight="600" fill="{TEXT}">On GitHub</text>')
    stats = [("Stars earned", d["stars"], ACCENT),
             ("Public repos", d["repos"], ACCENT2),
             ("Merged PRs", d["prs"], ACCENT3),
             ("Followers", d["followers"], "#f778ba")]
    cw = (W - 40) / 4
    for i, (label, val, color) in enumerate(stats):
        x = 20 + i * cw
        parts.append(f'<text x="{x:.0f}" y="84" font-family="{MONO}" font-size="27" '
                     f'font-weight="700" fill="{color}">{val:,}</text>')
        parts.append(f'<text x="{x:.0f}" y="106" font-family="{FONT}" font-size="12.5" '
                     f'fill="{TEXT_DIM}">{label}</text>')
    return svg_doc(W, H, "\n".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="sajxraj")
    ap.add_argument("--out", default="assets")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    d = fetch_data(a.user)
    src = out / ".avatar-src.png"
    if not src.exists():  # refresh avatar from GitHub
        req = urllib.request.Request(
            d["avatar_url"] + "&size=300", headers={"User-Agent": "profile-assets"})
        src.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    b64 = base64.b64encode(src.read_bytes()).decode()
    (out / "banner.svg").write_text(banner_svg(d, b64))
    (out / "heatmap.svg").write_text(heatmap_card(d))
    (out / "stats.svg").write_text(stats_card(d))
    print(f"wrote banner.svg heatmap.svg stats.svg to {out}/ "
          f"({d['calendar']['totalContributions']:,} contributions, "
          f"{d['stars']} stars, {d['prs']} PRs)")


if __name__ == "__main__":
    main()
