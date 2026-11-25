"""
Generates the terminal-style SVGs used in README.md.

  assets/header.svg         – intro terminal with typing animation
  assets/contributions.svg  – contribution heat-map (last 12 months)
  assets/whoami.svg         – animated ASCII portrait + live stats
  assets/footer.svg         – sign-off terminal
  assets/ascii-portrait.svg – large standalone portrait (build_portrait.py)

Runs daily in GitHub Actions (stdlib only, no pip install needed).
  python scripts/generate_profile.py              # live data (needs GITHUB_TOKEN)
  python scripts/generate_profile.py --demo       # fake data for local preview
  python scripts/generate_profile.py --placeholder
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
LOGIN = os.environ.get("PROFILE_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "kfrimer"
USER = "kfrimer"

# ── palette (GitHub dark) ────────────────────────────────────────────────
BG = "#010409"
WIN = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
FG = "#e6edf3"
MUTED = "#7d8590"
DIM = "#484f58"
GREEN = "#3fb950"
BRIGHT = "#56d364"
BLUE = "#58a6ff"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
W = 1000


# ── helpers ──────────────────────────────────────────────────────────────
def svg_open(h, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" font-family="{MONO}">
<style>
text{{font-family:{MONO}}}
.cur{{animation:blink 1.05s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
.fade{{opacity:0;animation:fade .6s ease-out forwards}}
@keyframes fade{{to{{opacity:1}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important;transform:none!important}}}}
</style>
<rect x="0.5" y="0.5" width="{W-1}" height="{h-1}" rx="14" fill="{BG}" stroke="#21262d"/>
"""


def window(x, y, w, h, title):
    return f"""<g>
<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="10" fill="{WIN}" stroke="{BORDER}"/>
<path d="M{x+.5} {y+30} V{y+10.5} a10 10 0 0 1 10 -10 H{x+w-10.5} a10 10 0 0 1 10 10 V{y+30} Z" fill="{BAR}"/>
<line x1="{x+.5}" y1="{y+30.5}" x2="{x+w-.5}" y2="{y+30.5}" stroke="{BORDER}"/>
<circle cx="{x+17}" cy="{y+15.5}" r="5.5" fill="#ff5f57"/><circle cx="{x+35}" cy="{y+15.5}" r="5.5" fill="#febc2e"/><circle cx="{x+53}" cy="{y+15.5}" r="5.5" fill="#28c840"/>
<text x="{x+w/2}" y="{y+20}" fill="{MUTED}" font-size="11.5" text-anchor="middle">{escape(title)}</text>
</g>
"""


_clip_id = [0]


def typed(x, y, parts, size=15, begin=0.0, cps=26, weight="700", cursor=False):
    """Prompt line revealed character-by-character (SMIL, works in <img>)."""
    _clip_id[0] += 1
    cid = f"t{_clip_id[0]}"
    text = "".join(t for t, _ in parts)
    n = len(text)
    cw = size * 0.6
    dur = max(0.3, n / cps)
    vals = ";".join(f"{i*cw:.1f}" for i in range(n + 1)) + f";{n*cw+40:.1f}"
    out = [f'<clipPath id="{cid}"><rect x="{x}" y="{y-size}" width="0" height="{size*1.6}">'
           f'<animate attributeName="width" values="{vals}" dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze" calcMode="discrete"/></rect></clipPath>']
    spans = "".join(f'<tspan fill="{c}">{escape(t)}</tspan>' for t, c in parts)
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" clip-path="url(#{cid})" xml:space="preserve">{spans}</text>')
    if cursor:
        out.append(f'<rect class="cur" x="{x+n*cw+3:.1f}" y="{y-size+2}" width="{size*0.55:.1f}" height="{size+1}" fill="{GREEN}" opacity="0">'
                   f'<set attributeName="opacity" to="1" begin="{begin+dur:.2f}s" fill="freeze"/></rect>')
    return "\n".join(out), begin + dur


def prompt(cmd):
    return [(f"{USER}@github", GREEN), (" ~ ", BLUE), ("$ ", MUTED), (cmd, FG)]


def save(name, content):
    path = os.path.join(ASSETS, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote {os.path.relpath(path, ROOT)}  ({len(content.encode())/1024:.0f} KB)")


def fmt_day(d, year=False):
    s = d.strftime("%b %-d") if os.name != "nt" else d.strftime("%b %#d")
    return s + (d.strftime(", %Y") if year else "")


# ── data ─────────────────────────────────────────────────────────────────
def fetch_days():
    token = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("No GITHUB_TOKEN – run with --demo for a local preview.")
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
           totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-readme-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(json.dumps(payload["errors"], indent=2))
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def demo_days(empty=False):
    today = dt.date.today()
    start = today - dt.timedelta(days=364 + (today.weekday() + 1) % 7)
    rnd = random.Random(7)
    days = []
    d = start
    while d <= today:
        if empty:
            c = 0
        else:
            busy = 0.55 + 0.4 * ((d - start).days / 365)
            c = 0 if rnd.random() > busy else int(rnd.expovariate(1 / 6)) + 1
        days.append((d, c))
        d += dt.timedelta(days=1)
    return days


def compute(days):
    days = sorted(days)
    today = days[-1][0]
    total = sum(c for _, c in days)
    best = max(days, key=lambda x: x[1])
    # current streak (today may still be empty → start from yesterday)
    i = len(days) - 1
    if days[i][1] == 0:
        i -= 1
    cur, end_i = 0, i
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    cur_range = (days[i + 1][0], days[end_i][0]) if cur else None
    longest = run = 0
    long_range = None
    for k, (d, c) in enumerate(days):
        run = run + 1 if c else 0
        if run and run >= longest:
            longest = run
            long_range = (days[k - run + 1][0], d)
    active = sum(1 for _, c in days if c)
    return dict(days=days, today=today, total=total, best=best, cur=cur,
                cur_range=cur_range, longest=longest, long_range=long_range, active=active)


# ── portrait ─────────────────────────────────────────────────────────────
def load_portrait():
    with open(os.path.join(ASSETS, "src", "portrait.json"), encoding="utf-8") as f:
        return json.load(f)


def portrait_rows(p, x0, y0, cw, ch, fs, start=0.0, step=0.035):
    # every glyph gets an explicit x → exact grid regardless of the viewer's mono font
    out = [f'<g font-size="{fs}">']
    for r, runs in enumerate(p["data"]):
        col = 0
        spans = []
        for c, t in runs:
            if c is not None:
                xs = " ".join(f"{round(x0 + (col + k) * cw, 1):g}" for k in range(len(t)))
                spans.append(f'<tspan x="{xs}" fill="{c}">{escape(t)}</tspan>')
            col += len(t)
        if not spans:
            continue
        out.append(f'<text class="pr" y="{y0 + (r+1)*ch:g}" style="animation-delay:{start + r*step:.2f}s">{"".join(spans)}</text>')
    out.append("</g>")
    return "\n".join(out)


PORTRAIT_CSS = """.pr{opacity:0;animation:pin .45s ease-out forwards}
@keyframes pin{0%{opacity:0}40%{opacity:1;fill:#fff}100%{opacity:1}}"""


def scanline(x, y, w, h, begin, dur):
    return (f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{BRIGHT}" stop-opacity=".55"/></linearGradient>'
            f'<rect x="{x}" y="{y-24}" width="{w}" height="24" fill="url(#scan)" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
            f'<animate attributeName="y" from="{y-24}" to="{y+h-24}" begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" from="1" to="0" begin="{begin+dur:.2f}s" dur=".4s" fill="freeze"/></rect>')


def write_standalone_portrait():
    p = load_portrait()
    cw, ch = 11.4, 19
    w = round(p["cols"] * cw + 60)
    h = round(p["rows"] * ch + 60)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<style>text{{font-family:{MONO}}}{PORTRAIT_CSS}'
           f'@media (prefers-reduced-motion:reduce){{.pr{{animation:none;opacity:1}}}}</style>'
           f'<rect width="100%" height="100%" fill="{WIN}"/>'
           + portrait_rows(p, 30, 26, cw, ch, 19, 0.2, 0.04) + "</svg>")
    save("ascii-portrait.svg", svg)


# ── SVG builders ─────────────────────────────────────────────────────────
def build_header():
    h = 210
    s = [svg_open(h)]
    s.append(window(20, 20, W - 40, h - 40, f"{USER} — zsh — 120×24"))
    line, t = typed(44, 82, prompt("whoami --short"), begin=0.3)
    s.append(line)
    s.append(f'<g class="fade" style="animation-delay:{t+.15:.2f}s">'
             f'<text x="44" y="124" font-size="30" font-weight="700" fill="{FG}">Kristián Frimer</text>'
             f'<text x="44" y="150" font-size="14" fill="{MUTED}">IT student <tspan fill="{DIM}">@</tspan> SPŠE Prešov '
             f'<tspan fill="{DIM}">·</tspan> founder of <tspan fill="{BRIGHT}">OutfititLab</tspan> '
             f'<tspan fill="{DIM}">·</tspan> Apple &amp; mobile developer <tspan fill="{DIM}">·</tspan> 🇸🇰</text></g>')
    line, _ = typed(44, 176, prompt(""), begin=t + 0.7, cursor=True)
    s.append(line)
    s.append("</svg>")
    save("header.svg", "\n".join(s))


def build_contributions(st, placeholder=False):
    cell, gap = 13, 3
    step = cell + gap
    days = st["days"]
    first = days[0][0]
    # align to Sunday-start weeks like GitHub
    offset = (first.weekday() + 1) % 7
    ncols = (offset + len(days) + 6) // 7
    grid_w = ncols * step - gap
    left = 40
    x0 = (W - (grid_w + left)) / 2 + left
    win_y = 52
    y0 = win_y + 30 + 46
    h = y0 + 7 * step + 64
    css = ".c{opacity:0;animation:fade .5s ease-out forwards}"
    s = [svg_open(h, css)]
    line, t = typed(24, 34, prompt("./contributions --last-year"), begin=0.2)
    s.append(line)
    s.append(window(20, win_y, W - 40, h - win_y - 20, "contributions — last 12 months"))
    nonzero = sorted(c for _, c in days if c)
    q = [nonzero[int(len(nonzero) * f)] for f in (0.25, 0.5, 0.75)] if nonzero else [1, 2, 3]

    def level(c):
        if c == 0:
            return 0
        return 1 + sum(c > v for v in q)

    # month labels
    labels = []
    prev = None
    for col in range(ncols):
        i = max(0, col * 7 - offset)
        if i >= len(days):
            break
        m = days[i][0].month
        if m != prev:
            labels.append((col, days[i][0]))
            prev = m
    if len(labels) > 1 and labels[1][0] - labels[0][0] < 3:
        labels.pop(0)  # partial first month would collide
    for col, d in labels:
        s.append(f'<text x="{x0 + col*step:.1f}" y="{y0 - 10}" font-size="11" fill="{MUTED}">{d.strftime("%b")}</text>')
    for r, lbl in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.append(f'<text x="{x0 - 10:.1f}" y="{y0 + r*step + 10}" font-size="10.5" fill="{MUTED}" text-anchor="end">{lbl}</text>')
    for i, (d, c) in enumerate(days):
        col, row = divmod(offset + i, 7)
        delay = t + 0.15 + col * 0.022
        s.append(f'<rect class="c" style="animation-delay:{delay:.2f}s" x="{x0 + col*step:.1f}" y="{y0 + row*step}" '
                 f'width="{cell}" height="{cell}" rx="2.5" fill="{LEVELS[level(c)]}"><title>{c} on {d.isoformat()}</title></rect>')
    fy = y0 + 7 * step + 26
    total = "—" if placeholder else f"{st['total']:,}"
    s.append(f'<text x="{x0:.1f}" y="{fy}" font-size="12.5" fill="{FG}" font-weight="700">{total} '
             f'<tspan fill="{MUTED}" font-weight="400">contributions in the last year</tspan>'
             f'<tspan fill="{DIM}" font-weight="400">  ·  {"syncing…" if placeholder else str(st["active"]) + " active days"}</tspan></text>')
    lx = x0 + grid_w - 5 * 15 - 36
    s.append(f'<text x="{lx - 8:.1f}" y="{fy}" font-size="11" fill="{MUTED}" text-anchor="end">less</text>')
    for k, colr in enumerate(LEVELS):
        s.append(f'<rect x="{lx + k*15:.1f}" y="{fy - 10}" width="11" height="11" rx="2" fill="{colr}"/>')
    s.append(f'<text x="{lx + 5*15 + 4:.1f}" y="{fy}" font-size="11" fill="{MUTED}">more</text>')
    s.append("</svg>")
    save("contributions.svg", "\n".join(s))


def build_whoami(st, placeholder=False):
    p = load_portrait()
    cw, ch, fs = 5.4, 9, 9
    pw = p["cols"] * cw
    ph = p["rows"] * ch
    win_y = 52
    left_w = round(pw + 40)
    win_h = round(ph + 30 + 34)
    h = win_y + win_h + 20
    right_x = 20 + left_w + 16
    right_w = W - 20 - right_x
    css = PORTRAIT_CSS + """
.bar{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);animation:grow .7s cubic-bezier(.2,.8,.2,1) forwards}
@keyframes grow{to{transform:scaleY(1)}}"""
    s = [svg_open(h, css)]
    line, t = typed(24, 34, prompt("whoami"), begin=0.2)
    s.append(line)

    # left: portrait
    s.append(window(20, win_y, left_w, win_h, "portrait.txt — ascii"))
    px, py = 40, win_y + 30 + 14
    start = t + 0.2
    s.append(portrait_rows(p, px, py, cw, ch, fs, start, 0.035))
    s.append(scanline(21, py, left_w - 2, ph + 10, start, p["rows"] * 0.035 + 0.3))

    # right: stats
    s.append(window(right_x, win_y, right_w, win_h, "stats — live"))
    x = right_x + 24
    y = win_y + 30
    d0 = start + 0.3
    dash = "—"

    def block(yy, cmd, big, unit, sub, color, delay):
        return (f'<g class="fade" style="animation-delay:{delay:.2f}s">'
                f'<text x="{x}" y="{yy}" font-size="12" fill="{MUTED}"><tspan fill="{GREEN}">$</tspan> {escape(cmd)}</text>'
                f'<text x="{x}" y="{yy+40}" font-size="34" font-weight="700" fill="{color}">{big}'
                f'<tspan font-size="14" font-weight="400" fill="{MUTED}"> {unit}</tspan></text>'
                f'<text x="{x}" y="{yy+58}" font-size="11" fill="{DIM}">{escape(sub)}</text></g>')

    if placeholder:
        subs = ["syncing with GitHub…"] * 4
        vals = [dash] * 4
    else:
        cr, lr = st["cur_range"], st["long_range"]
        subs = [f"{fmt_day(cr[0])} – {fmt_day(cr[1])}" if cr else "start one today",
                f"{fmt_day(lr[0])} – {fmt_day(lr[1])}" if lr else "—",
                f"in the last year  ·  {st['active']} active days",
                fmt_day(st["best"][0], year=True)]
        vals = [str(st["cur"]), str(st["longest"]), f"{st['total']:,}", str(st["best"][1])]
    s.append(block(y + 32, "current streak", vals[0], "days", subs[0], BRIGHT, d0))
    s.append(block(y + 116, "longest streak", vals[1], "days", subs[1], FG, d0 + 0.2))
    s.append(block(y + 200, "contributions --year", vals[2], "", subs[2], FG, d0 + 0.4))
    s.append(block(y + 284, "best day", vals[3], "contributions", subs[3], FG, d0 + 0.6))

    # 30-day activity bars
    by = y + 378
    s.append(f'<text class="fade" style="animation-delay:{d0+0.8:.2f}s" x="{x}" y="{by}" font-size="12" fill="{MUTED}">'
             f'<tspan fill="{GREEN}">$</tspan> activity --last 30d</text>')
    last = [c for _, c in st["days"][-30:]]
    chart_w = right_w - 48
    chart_top = by + 18
    chart_bottom = win_y + win_h - 40
    chart_h = max(40, chart_bottom - chart_top)
    mx = max(last) if last and max(last) else 1
    bw = chart_w / 30
    s.append(f'<line x1="{x}" y1="{chart_bottom + .5}" x2="{x + chart_w}" y2="{chart_bottom + .5}" stroke="{BORDER}"/>')
    for i, c in enumerate(last):
        bh = 3 if c == 0 else max(5, c / mx * chart_h)
        colr = BAR if c == 0 else (BRIGHT if c == mx else LEVELS[3] if c > mx * .5 else LEVELS[2])
        s.append(f'<rect class="bar" style="animation-delay:{d0 + 0.9 + i*0.03:.2f}s" x="{x + i*bw + 1.5:.1f}" '
                 f'y="{chart_bottom - bh:.1f}" width="{bw - 3:.1f}" height="{bh:.1f}" rx="1.5" fill="{colr}"/>')
    s.append(f'<text x="{x}" y="{chart_bottom + 18}" font-size="10" fill="{DIM}">30d ago</text>')
    s.append(f'<text x="{x + chart_w}" y="{chart_bottom + 18}" font-size="10" fill="{DIM}" text-anchor="end">today</text>')
    s.append("</svg>")
    save("whoami.svg", "\n".join(s))


def build_footer(st, placeholder=False):
    h = 132
    s = [svg_open(h)]
    s.append(window(20, 16, W - 40, h - 32, "~ — goodbye"))
    line, t = typed(44, 76, prompt('echo "thanks for visiting"'), begin=0.3)
    s.append(line)
    s.append(f'<text class="fade" style="animation-delay:{t+.2:.2f}s" x="44" y="100" font-size="14" fill="{MUTED}">'
             f'thanks for visiting <tspan fill="{BRIGHT}">✦</tspan> see you in the next commit</text>')
    upd = "" if placeholder else f"last sync {dt.date.today():%Y-%m-%d}"
    s.append(f'<text x="{W-44}" y="100" font-size="10.5" fill="{DIM}" text-anchor="end">{upd}</text>')
    s.append("</svg>")
    save("footer.svg", "\n".join(s))


def main():
    os.makedirs(ASSETS, exist_ok=True)
    placeholder = "--placeholder" in sys.argv
    if "--demo" in sys.argv:
        days = demo_days()
    elif placeholder:
        days = demo_days(empty=True)
    else:
        days = fetch_days()
    st = compute(days)
    build_header()
    build_contributions(st, placeholder)
    build_whoami(st, placeholder)
    build_footer(st, placeholder)


if __name__ == "__main__":
    main()
