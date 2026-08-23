#!/usr/bin/env python3
"""Self-hosted replacement for github-readme-streak-stats / activity-graph.
Pulls real contribution data via `gh api graphql` and renders two SVGs
(assets/analytics.svg, assets/contribution-graph.svg) into this repo so the
README no longer depends on flaky third-party rendering services.
"""
import subprocess
import json
import datetime
import os
import sys

LOGIN = "walterwhite91"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

MUTE = "#7d9fc4"
ACCENT = "#9f8cff"


def gh_graphql(query, **fields):
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in fields.items():
        args += ["-f", f"{k}={v}"]
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        raise SystemExit(out.returncode)
    return json.loads(out.stdout)


def fetch_all_days():
    created_q = "query($login:String!){user(login:$login){createdAt}}"
    created = gh_graphql(created_q, login=LOGIN)["data"]["user"]["createdAt"]
    created_dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)

    cal_q = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }"""

    days = {}
    cursor = created_dt
    while cursor < now:
        nxt = min(cursor + datetime.timedelta(days=365), now)
        data = gh_graphql(cal_q, login=LOGIN, **{"from": cursor.isoformat(), "to": nxt.isoformat()})
        cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                days[day["date"]] = day["contributionCount"]
        cursor = nxt
    return days, created_dt, now


def compute_streaks(days, now):
    dates = sorted(days.keys())
    today_str = now.date().isoformat()

    longest = 0
    longest_start = longest_end = None
    run = run_start = 0, None
    run, run_start = 0, None
    for d in dates:
        if days[d] > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, longest_start, longest_end = run, run_start, d
        else:
            run = 0

    current = 0
    cur_start = cur_end = None
    for d in reversed(dates):
        if d > today_str:
            continue
        if days[d] > 0:
            if current == 0:
                cur_end = d
            current += 1
            cur_start = d
        else:
            if d == today_str:
                continue
            break

    return {
        "longest": longest, "longest_start": longest_start, "longest_end": longest_end,
        "current": current, "current_start": cur_start, "current_end": cur_end,
    }


def fmt_range(a, b):
    def short(d):
        dt = datetime.date.fromisoformat(d)
        return dt.strftime("%b %-d") if os.name != "nt" else dt.strftime("%b %d").replace(" 0", " ")
    if a == b:
        return short(a)
    return f"{short(a)} - {short(b)}"


def transparent_theme_css():
    """Theme-aware blueprint ink on a fully transparent canvas."""
    return '''<style>
    .ink-text { fill: #3d3846; }
    .mute-text { fill: #607d9b; }
    .accent-text { fill: #6f5bd3; }
    .guide { stroke: #7d9fc4; }
    .accent-stroke { stroke: #6f5bd3; }
    .data-point { fill: #3d3846; stroke: #6f5bd3; }
    .accent-stop { stop-color: #6f5bd3; }
    .live-dot { fill: #6f5bd3; animation: livePulse 5s ease-in-out infinite; }
    .trace { animation: traceDraw 10s ease-in-out infinite; }
    @keyframes livePulse { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }
    @keyframes traceDraw {
      0% { stroke-dasharray: 0 1; opacity: .35; }
      28%, 86% { stroke-dasharray: 1 0; opacity: 1; }
      100% { stroke-dasharray: 0 1; opacity: .35; }
    }
    @media (prefers-color-scheme: dark) {
      .ink-text { fill: #f1ece1; }
      .mute-text { fill: #7d9fc4; }
      .accent-text { fill: #9f8cff; }
      .guide { stroke: #7d9fc4; }
      .accent-stroke { stroke: #9f8cff; }
      .data-point { fill: #f1ece1; stroke: #9f8cff; }
      .accent-stop { stop-color: #9f8cff; }
      .live-dot { fill: #9f8cff; }
    }
    @media (prefers-reduced-motion: reduce) {
      .live-dot, .trace { animation: none; }
    }
  </style>'''


def render_analytics(total, since_dt, streaks):
    since_label = since_dt.strftime("%b %-d, %Y")
    cur = streaks["current"]
    longest = streaks["longest"]
    cur_range = fmt_range(streaks["current_start"], streaks["current_end"]) if cur else "--"
    longest_range = fmt_range(streaks["longest_start"], streaks["longest_end"]) if longest else "--"

    r = 34
    circumference = 2 * 3.14159265 * r
    frac = min(cur / 14.0, 1.0) if cur else 0.0
    dash = circumference * frac

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="220" viewBox="0 0 760 220" role="img" aria-label="GitHub analytics: {total} total contributions since {since_label}, current streak {cur} days ({cur_range}), longest streak {longest} days ({longest_range})">
  {transparent_theme_css()}

  <text x="28" y="20" class="mute-text" font-family="ui-monospace, monospace" font-size="10" letter-spacing="2">FIG. 02    GITHUB ANALYTICS</text>
  <text x="730" y="20" text-anchor="end" class="mute-text" font-family="ui-monospace, monospace" font-size="10" letter-spacing="1.6">LIVE DATA · @WALTERWHITE91</text>
  <circle class="live-dot" cx="740" cy="16" r="2.5" />
  <line x1="20" y1="32" x2="740" y2="32" class="guide" stroke-opacity=".52" />
  <path d="M14 32h12M20 26v12M734 32h12M740 26v12M14 184h12M20 178v12M734 184h12M740 178v12" class="guide" fill="none" />

  <line x1="253" y1="54" x2="253" y2="166" class="guide" stroke-opacity=".28" />
  <line x1="507" y1="54" x2="507" y2="166" class="guide" stroke-opacity=".28" />

  <g text-anchor="middle" font-family="Inter, system-ui, sans-serif">
    <text x="126" y="104" font-size="36" font-weight="800" class="ink-text">{total}</text>
    <text x="126" y="132" font-size="12" font-weight="650" class="ink-text">Total Contributions</text>
    <text x="126" y="153" font-size="10" font-family="ui-monospace, monospace" class="mute-text">{since_label} — Present</text>

    <circle cx="380" cy="94" r="{r}" fill="none" class="accent-stroke" stroke-opacity=".18" stroke-width="5" />
    <circle cx="380" cy="94" r="{r}" fill="none" class="accent-stroke" stroke-width="5" stroke-linecap="round"
      stroke-dasharray="{dash:.2f} {circumference:.2f}" transform="rotate(-90 380 94)" />
    <text x="380" y="102" font-size="25" font-weight="800" class="ink-text">{cur}</text>
    <text x="380" y="140" font-size="12" font-weight="700" class="ink-text">Current Streak</text>
    <text x="380" y="158" font-size="10" font-family="ui-monospace, monospace" class="mute-text">{cur_range}</text>

    <text x="633" y="104" font-size="36" font-weight="800" class="ink-text">{longest}</text>
    <text x="633" y="132" font-size="12" font-weight="650" class="ink-text">Longest Streak</text>
    <text x="633" y="153" font-size="10" font-family="ui-monospace, monospace" class="mute-text">{longest_range}</text>
  </g>

  <line x1="20" y1="184" x2="740" y2="184" class="guide" stroke-opacity=".52" />
  <g class="mute-text" font-family="ui-monospace, monospace" font-size="8" letter-spacing="1.25">
    <text x="28" y="204">SOURCE / GITHUB GRAPHQL</text>
    <text x="380" y="204" text-anchor="middle">WINDOW / ACCOUNT LIFETIME</text>
    <text x="732" y="204" text-anchor="end">REFRESH / DAILY</text>
  </g>
</svg>
'''
    with open(os.path.join(ASSETS, "analytics.svg"), "w") as f:
        f.write(svg)


def smooth_path(points):
    """Catmull-Rom -> cubic bezier through points, for a soft line like the reference chart."""
    if len(points) < 2:
        return ""
    pts = [points[0]] + points + [points[-1]]
    d = f"M {pts[1][0]:.2f} {pts[1][1]:.2f} "
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d += f"C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {p2[0]:.2f} {p2[1]:.2f} "
    return d


def render_contribution_graph(days):
    dates = sorted(days.keys())[-31:]
    counts = [days[d] for d in dates]
    max_val = max(max(counts), 10)
    # round max up to a "nice" step
    step = 10
    while step * 7 < max_val:
        step += 10
    top = step * 7

    left, right, top_pad, bottom = 60, 730, 60, 260
    plot_w = right - left
    plot_h = bottom - top_pad
    n = len(dates)

    def px(i):
        return left + (plot_w * i / (n - 1)) if n > 1 else left
    def py(v):
        return bottom - (plot_h * v / top)

    points = [(px(i), py(c)) for i, c in enumerate(counts)]
    line_path = smooth_path(points)
    area_path = line_path + f"L {points[-1][0]:.2f} {bottom:.2f} L {points[0][0]:.2f} {bottom:.2f} Z"

    grid_lines = []
    y_labels = []
    for k in range(8):
        val = step * k
        y = py(val)
        grid_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="{MUTE}" stroke-opacity=".18" stroke-dasharray="3 4" />')
        y_labels.append(f'<text x="{left-14}" y="{y+4:.2f}" text-anchor="end" font-size="10" fill="{MUTE}" font-family="ui-monospace, monospace">{val}</text>')

    x_labels = []
    for i, d in enumerate(dates):
        if i % 3 != 0 and i != len(dates) - 1:
            continue
        day_num = int(d.split("-")[2])
        x_labels.append(f'<text x="{px(i):.2f}" y="{bottom+18}" text-anchor="middle" font-size="10" fill="{MUTE}" font-family="ui-monospace, monospace">{day_num}</text>')

    dots = []
    for i, (x, y) in enumerate(points):
        if counts[i] > 0:
            dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.4" class="data-point" stroke-width="1.4" />')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="320" viewBox="0 0 760 320" role="img" aria-label="Mimansh's contribution graph, last 31 days">
  {transparent_theme_css()}
  <defs>
    <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" class="accent-stop" stop-opacity=".28" />
      <stop offset="1" class="accent-stop" stop-opacity="0" />
    </linearGradient>
  </defs>

  <text x="28" y="20" class="mute-text" font-family="ui-monospace, monospace" font-size="10" letter-spacing="2">FIG. 03    CONTRIBUTION TRACE</text>
  <text x="730" y="20" text-anchor="end" class="mute-text" font-family="ui-monospace, monospace" font-size="10" letter-spacing="1.6">31 DAY WINDOW · LIVE</text>
  <circle class="live-dot" cx="740" cy="16" r="2.5" />
  <line x1="20" y1="32" x2="740" y2="32" class="guide" stroke-opacity=".52" />
  <path d="M14 32h12M20 26v12M734 32h12M740 26v12M14 286h12M20 280v12M734 286h12M740 280v12" class="guide" fill="none" />

  <g>{''.join(grid_lines)}</g>
  <g>{''.join(y_labels)}</g>
  <g>{''.join(x_labels)}</g>
  <text x="20" y="{top_pad + plot_h/2:.2f}" text-anchor="middle" font-size="10" class="mute-text" font-family="ui-monospace, monospace" transform="rotate(-90 20 {top_pad + plot_h/2:.2f})">Contributions</text>

  <path d="{area_path}" fill="url(#areaFill)" stroke="none" />
  <path class="trace accent-stroke" pathLength="1" d="{line_path}" fill="none" stroke-width="2.2" stroke-linecap="round" />
  {''.join(dots)}

  <line x1="20" y1="286" x2="740" y2="286" class="guide" stroke-opacity=".52" />
  <g class="mute-text" font-family="ui-monospace, monospace" font-size="8" letter-spacing="1.25">
    <text x="28" y="306">SOURCE / GITHUB GRAPHQL</text>
    <text x="380" y="306" text-anchor="middle">WINDOW / LAST 31 DAYS</text>
    <text x="732" y="306" text-anchor="end">REFRESH / DAILY</text>
  </g>
</svg>
'''
    with open(os.path.join(ASSETS, "contribution-graph.svg"), "w") as f:
        f.write(svg)


def main():
    days, created_dt, now = fetch_all_days()
    total = sum(days.values())
    streaks = compute_streaks(days, now)
    render_analytics(total, created_dt, streaks)
    render_contribution_graph(days)
    print(f"total={total} current={streaks['current']} longest={streaks['longest']}")


if __name__ == "__main__":
    main()
