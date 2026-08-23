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

PAPER = ["#302d39", "#3d3846", "#353248"]
INK = "#f1ece1"
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

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="200" viewBox="0 0 760 200" role="img" aria-label="GitHub analytics: {total} total contributions since {since_label}, current streak {cur} days ({cur_range}), longest streak {longest} days ({longest_range})">
  <defs>
    <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{PAPER[0]}" />
      <stop offset="0.58" stop-color="{PAPER[1]}" />
      <stop offset="1" stop-color="{PAPER[2]}" />
    </linearGradient>
  </defs>
  <rect width="760" height="200" rx="10" fill="url(#paper)" stroke="{INK}" stroke-opacity=".14" />

  <line x1="253" y1="36" x2="253" y2="164" stroke="{MUTE}" stroke-opacity=".3" />
  <line x1="507" y1="36" x2="507" y2="164" stroke="{MUTE}" stroke-opacity=".3" />

  <g text-anchor="middle" font-family="Inter, system-ui, sans-serif">
    <text x="126" y="86" font-size="34" font-weight="800" fill="{INK}">{total}</text>
    <text x="126" y="114" font-size="12" fill="{INK}" fill-opacity=".85">Total Contributions</text>
    <text x="126" y="136" font-size="11" font-family="ui-monospace, monospace" fill="{MUTE}">{since_label} - Present</text>

    <circle cx="380" cy="76" r="{r}" fill="none" stroke="{ACCENT}" stroke-opacity=".22" stroke-width="5" />
    <circle cx="380" cy="76" r="{r}" fill="none" stroke="{ACCENT}" stroke-width="5" stroke-linecap="round"
      stroke-dasharray="{dash:.2f} {circumference:.2f}" transform="rotate(-90 380 76)" />
    <text x="380" y="83" font-size="24" font-weight="800" fill="{INK}">{cur}</text>
    <text x="380" y="114" font-size="12" font-weight="700" fill="{INK}" fill-opacity=".85">Current Streak</text>
    <text x="380" y="136" font-size="11" font-family="ui-monospace, monospace" fill="{MUTE}">{cur_range}</text>

    <text x="633" y="86" font-size="34" font-weight="800" fill="{INK}">{longest}</text>
    <text x="633" y="114" font-size="12" fill="{INK}" fill-opacity=".85">Longest Streak</text>
    <text x="633" y="136" font-size="11" font-family="ui-monospace, monospace" fill="{MUTE}">{longest_range}</text>
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
        day_num = int(d.split("-")[2])
        x_labels.append(f'<text x="{px(i):.2f}" y="{bottom+18}" text-anchor="middle" font-size="10" fill="{MUTE}" font-family="ui-monospace, monospace">{day_num}</text>')

    dots = []
    for i, (x, y) in enumerate(points):
        if counts[i] > 0:
            dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.4" fill="{INK}" stroke="{ACCENT}" stroke-width="1.4" />')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="320" viewBox="0 0 760 320" role="img" aria-label="Mimansh's contribution graph, last 31 days">
  <defs>
    <linearGradient id="paper2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{PAPER[0]}" />
      <stop offset="0.58" stop-color="{PAPER[1]}" />
      <stop offset="1" stop-color="{PAPER[2]}" />
    </linearGradient>
    <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity=".38" />
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0" />
    </linearGradient>
  </defs>
  <rect width="760" height="320" rx="10" fill="url(#paper2)" stroke="{INK}" stroke-opacity=".14" />
  <text x="380" y="34" text-anchor="middle" font-size="15" font-weight="700" fill="{INK}" font-family="Inter, system-ui, sans-serif">Mimansh's Contribution Graph</text>

  <g>{''.join(grid_lines)}</g>
  <g>{''.join(y_labels)}</g>
  <g>{''.join(x_labels)}</g>
  <text x="20" y="{top_pad + plot_h/2:.2f}" text-anchor="middle" font-size="10" fill="{MUTE}" font-family="ui-monospace, monospace" transform="rotate(-90 20 {top_pad + plot_h/2:.2f})">Contributions</text>
  <text x="{left + plot_w/2:.2f}" y="304" text-anchor="middle" font-size="10" fill="{MUTE}" font-family="ui-monospace, monospace">Days</text>

  <path d="{area_path}" fill="url(#areaFill)" stroke="none" />
  <path d="{line_path}" fill="none" stroke="{ACCENT}" stroke-width="2.2" stroke-linecap="round" />
  {''.join(dots)}
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
