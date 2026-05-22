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

    # 兼容三种历史结构：
    #   - {spelling, date}                  → note_date=date
    #   - {spelling, note_date, phrase_date} → 直接读
    #   - 纯字符串 spelling                 → 无日期，跳过
    notes_daily   = defaultdict(int)
    phrases_daily = defaultdict(int)
    for voc_id, val in data.items():
        if not isinstance(val, dict):
            continue
        note_date   = val.get("note_date") or val.get("date")
        phrase_date = val.get("phrase_date")
        if note_date and note_date != "unknown":
            notes_daily[note_date] += 1
        if phrase_date and phrase_date != "unknown":
            phrases_daily[phrase_date] += 1

    if not notes_daily and not phrases_daily:
        print("没有带日期的记录，跳过生成图表。")
        return

    # 用两条曲线共享的 X 轴（所有出现过的日期）
    sorted_dates = sorted(set(notes_daily) | set(phrases_daily))

    def cumulative_of(daily):
        out, total = [], 0
        for d in sorted_dates:
            total += daily.get(d, 0)
            out.append(total)
        return out

    notes_cum   = cumulative_of(notes_daily)
    phrases_cum = cumulative_of(phrases_daily)

    total_notes   = notes_cum[-1] if notes_cum else 0
    total_phrases = phrases_cum[-1] if phrases_cum else 0
    print(f"共 {len(sorted_dates)} 天数据，累计助记 {total_notes} 词、例句 {total_phrases} 词")

    svg = render_svg(sorted_dates, notes_cum, phrases_cum, total_notes, total_phrases)
    with open(CHART_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"chart.svg 已生成")


def render_svg(dates, notes_cum, phrases_cum, total_notes, total_phrases):
    W, H = 800, 280
    ML, MR, MT, MB = 55, 20, 40, 45  # margins
    pw = W - ML - MR  # plot width
    ph = H - MT - MB  # plot height

    n = len(dates)
    max_c = max(max(notes_cum, default=0), max(phrases_cum, default=0), 1)

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

    def polyline_points(series):
        return " ".join(f"{px(i):.1f},{py(c):.1f}" for i, c in enumerate(series))

    notes_pts   = polyline_points(notes_cum)
    phrases_pts = polyline_points(phrases_cum)

    notes_fill = (f"{px(0):.1f},{MT + ph} " + notes_pts +
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

    # 助记：蓝色填充 + 实线
    lines.append(f'<polygon points="{notes_fill}" fill="#1f6feb" opacity="0.15"/>')
    lines.append(f'<polyline points="{notes_pts}" fill="none" '
                 f'stroke="#58a6ff" stroke-width="2" stroke-linejoin="round"/>')

    # 例句：紫色实线（只在有数据时画）
    if total_phrases > 0:
        lines.append(f'<polyline points="{phrases_pts}" fill="none" '
                     f'stroke="#bc8cff" stroke-width="2" stroke-linejoin="round"/>')

    # Dots at first and last for both series
    for series, color in [(notes_cum, "#58a6ff"), (phrases_cum, "#bc8cff")]:
        if max(series, default=0) == 0:
            continue
        for idx in [0, n - 1]:
            cx, cy = px(idx), py(series[idx])
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" '
                         f'fill="{color}" stroke="#0d1117" stroke-width="2"/>')

    # X-axis labels
    for idx, label in x_labels:
        x = px(idx)
        lines.append(f'<text x="{x:.1f}" y="{H-8}" fill="#8b949e" '
                     f'font-size="11" text-anchor="middle">{label}</text>')
        lines.append(f'<line x1="{x:.1f}" y1="{MT+ph}" x2="{x:.1f}" '
                     f'y2="{MT+ph+4}" stroke="#8b949e" stroke-width="1"/>')

    # Title
    title = f'累计：助记 {total_notes} 词 · 例句 {total_phrases} 词'
    lines.append(f'<text x="{W//2}" y="22" fill="#e6edf3" '
                 f'font-size="14" font-weight="bold" text-anchor="middle">'
                 f'{title}</text>')

    # Legend (top-right)
    lx = W - MR - 130
    lines.append(f'<rect x="{lx}" y="30" width="10" height="3" fill="#58a6ff"/>')
    lines.append(f'<text x="{lx+14}" y="34" fill="#8b949e" font-size="11">助记</text>')
    if total_phrases > 0:
        lines.append(f'<rect x="{lx+55}" y="30" width="10" height="3" fill="#bc8cff"/>')
        lines.append(f'<text x="{lx+69}" y="34" fill="#8b949e" font-size="11">例句</text>')

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
