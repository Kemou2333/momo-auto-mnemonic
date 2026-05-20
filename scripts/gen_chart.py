#!/usr/bin/env python3
"""
读取 processed.json，按日期统计累计词数，生成 SVG 折线图保存为 chart.svg。
由 GitHub Actions 自动触发，不需要任何第三方库。
"""

import json
import os
from collections import defaultdict
from datetime import datetime

PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "processed.json")
CHART_PATH     = os.path.join(os.path.dirname(__file__), "..", "chart.svg")


def main():
    with open(PROCESSED_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # 统计每天新增词数
    daily = defaultdict(int)
    for voc_id, val in data.items():
        if isinstance(val, dict):
            date = val.get("date", "unknown")
        else:
            date = "unknown"
        if date != "unknown":
            daily[date] += 1

    if not daily:
        print("没有带日期的记录，跳过生成图表。")
        return

    # 排序并计算累计
    sorted_dates = sorted(daily.keys())
    cumulative, total = [], 0
    for d in sorted_dates:
        total += daily[d]
        cumulative.append(total)

    total_words = cumulative[-1] if cumulative else 0
    print(f"共 {len(sorted_dates)} 天数据，累计 {total_words} 词")

    svg = render_svg(sorted_dates, cumulative, total_words)
    with open(CHART_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"chart.svg 已生成")


def render_svg(dates, counts, total):
    W, H = 800, 280
    ML, MR, MT, MB = 55, 20, 40, 45  # margins
    pw = W - ML - MR  # plot width
    ph = H - MT - MB  # plot height

    n = len(dates)
    max_c = max(counts)

    def px(i):
        return ML + pw * i / max(n - 1, 1)

    def py(c):
        return MT + ph * (1 - c / max_c)

    # Axis ticks
    y_ticks = 5
    x_labels = []
    step = max(1, n // 6)
    for i in range(0, n, step):
        x_labels.append((i, dates[i][5:]))  # MM-DD
    if (n - 1) % step != 0:
        x_labels.append((n - 1, dates[-1][5:]))

    # Build polyline points
    pts = " ".join(f"{px(i):.1f},{py(c):.1f}" for i, c in enumerate(counts))

    # Fill area under line
    fill_pts = (f"{px(0):.1f},{MT + ph} " + pts +
                f" {px(n-1):.1f},{MT + ph}")

    lines = []

    # Background
    lines.append(f'<rect width="{W}" height="{H}" fill="#0d1117"/>')

    # Grid lines (horizontal)
    for k in range(y_ticks + 1):
        yv = max_c * k / y_ticks
        y  = py(yv)
        lines.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML+pw}" y2="{y:.1f}" '
                     f'stroke="#21262d" stroke-width="1"/>')
        lines.append(f'<text x="{ML-6}" y="{y+4:.1f}" fill="#8b949e" '
                     f'font-size="11" text-anchor="end">{int(yv)}</text>')

    # Fill + line
    lines.append(f'<polygon points="{fill_pts}" fill="#1f6feb" opacity="0.15"/>')
    lines.append(f'<polyline points="{pts}" fill="none" '
                 f'stroke="#58a6ff" stroke-width="2" stroke-linejoin="round"/>')

    # Dots at first and last
    for idx in [0, n - 1]:
        cx, cy = px(idx), py(counts[idx])
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" '
                     f'fill="#58a6ff" stroke="#0d1117" stroke-width="2"/>')

    # X-axis labels
    for idx, label in x_labels:
        x = px(idx)
        lines.append(f'<text x="{x:.1f}" y="{H-8}" fill="#8b949e" '
                     f'font-size="11" text-anchor="middle">{label}</text>')
        lines.append(f'<line x1="{x:.1f}" y1="{MT+ph}" x2="{x:.1f}" '
                     f'y2="{MT+ph+4}" stroke="#8b949e" stroke-width="1"/>')

    # Title
    lines.append(f'<text x="{W//2}" y="22" fill="#e6edf3" '
                 f'font-size="14" font-weight="bold" text-anchor="middle">'
                 f'助记累计添加词数（共 {total} 词）</text>')

    # Axes
    lines.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+ph}" '
                 f'stroke="#30363d" stroke-width="1"/>')
    lines.append(f'<line x1="{ML}" y1="{MT+ph}" x2="{ML+pw}" y2="{MT+ph}" '
                 f'stroke="#30363d" stroke-width="1"/>')

    inner = "\n  ".join(lines)
    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {W} {H}">\n  {inner}\n</svg>\n')


if __name__ == "__main__":
    main()
