#!/usr/bin/env python3
"""Generate the Baelfyre rolling repository traffic profile card."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

SCHEMA_VERSION = "baelfyre.repository-traffic.v1"
WINDOW = "rolling_14_days"
DEFAULT_INPUT = Path("analytics/repository-traffic.json")
DEFAULT_OUTPUT = Path("assets/profile/portfolio-traffic-card.svg")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def number(value: int) -> str:
    return f"{value:,}"


def shorten(value: str, limit: int = 42) -> str:
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def load_data(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("repository traffic schema_version drift")
    if data.get("window") != WINDOW:
        raise ValueError("repository traffic window drift")
    if not isinstance(data.get("snapshots"), list):
        raise ValueError("repository traffic snapshots must be a list")
    return data


def latest_snapshot(data: dict) -> dict | None:
    snapshots = data["snapshots"]
    if not snapshots:
        return None
    if not all(isinstance(snapshot, dict) for snapshot in snapshots):
        raise ValueError("repository traffic snapshots must contain objects")
    return max(
        snapshots,
        key=lambda snapshot: (
            str(snapshot.get("snapshot_date", "")),
            str(snapshot.get("captured_at", "")),
        ),
    )


def summarize(snapshot: dict) -> dict:
    repositories = snapshot.get("repositories")
    if not isinstance(repositories, dict):
        raise ValueError("latest traffic snapshot repositories must be an object")
    available = []
    for repository, metrics in repositories.items():
        if not isinstance(metrics, dict):
            raise ValueError(f"traffic metrics for {repository} must be an object")
        if metrics.get("status") != "ok":
            continue
        views = metrics.get("views")
        clones = metrics.get("clones")
        values = (
            views.get("count") if isinstance(views, dict) else None,
            views.get("uniques") if isinstance(views, dict) else None,
            clones.get("count") if isinstance(clones, dict) else None,
            clones.get("uniques") if isinstance(clones, dict) else None,
        )
        if not all(isinstance(value, int) and value >= 0 for value in values):
            raise ValueError(f"valid traffic metrics are required for {repository}")
        available.append({"name": str(repository), "views": values[0], "view_uniques": values[1], "clones": values[2]})
    top = max(available, key=lambda item: (item["views"], item["name"]), default=None)
    return {
        "tracked": len(repositories),
        "available": len(available),
        "total_views": sum(item["views"] for item in available),
        "total_clones": sum(item["clones"] for item in available),
        "top": top,
        "snapshot_date": str(snapshot.get("snapshot_date", "Unknown date")),
    }

def text(x: int, y: int, value: object, size: int, fill: str, **attrs: object) -> str:
    extra = " ".join(f'{key.replace("_", "-")}="{escape(value)}"' for key, value in attrs.items())
    suffix = f" {extra}" if extra else ""
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}"{suffix}>{escape(value)}</text>'


def metric_card(x: int, label: str, value: str) -> str:
    return "\n".join(
        (
            f'<rect x="{x}" y="128" width="226" height="96" rx="16" fill="#111a2c" stroke="#293754"/>',
            text(x + 18, 157, label, 11, "#9aa9c4", letter_spacing=1.5),
            text(x + 18, 196, value, 26, "#f8fafc", font_weight=700),
        )
    )


def base_svg(content: str, description: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 430" width="1100" height="430" role="img" aria-labelledby="title description">
  <title id="title">Baelfyre portfolio traffic</title>
  <desc id="description">{escape(description)}</desc>
  <defs>
    <linearGradient id="surface" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#111827"/>
      <stop offset="0.55" stop-color="#15152c"/>
      <stop offset="1" stop-color="#101827"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#8b5cf6"/>
      <stop offset="1" stop-color="#38bdf8"/>
    </linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a78bfa"/>
      <stop offset="1" stop-color="#60a5fa"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#000000" flood-opacity="0.28"/>
    </filter>
  </defs>
  <rect x="10" y="10" width="1080" height="410" rx="28" fill="url(#surface)" stroke="#34405e" filter="url(#shadow)"/>
  <path d="M38 106H1062" stroke="#2b3652"/>
  <rect x="38" y="38" width="5" height="61" rx="2.5" fill="url(#accent)"/>
{content}
</svg>
'''

def placeholder_svg() -> str:
    content = "\n".join(
        (
            text(64, 66, "PORTFOLIO TRAFFIC", 14, "#c4b5fd", font_weight=700, letter_spacing=2.5),
            text(1036, 66, "ROLLING 14 DAYS", 12, "#93c5fd", font_weight=700, text_anchor="end", letter_spacing=1.8),
            text(64, 91, "GitHub repository activity", 16, "#94a3b8"),
            '<rect x="64" y="154" width="972" height="168" rx="20" fill="#111a2c" stroke="#293754"/>',
            '<circle cx="108" cy="211" r="23" fill="#241d45" stroke="#8b5cf6"/>',
            text(99, 219, "+", 25, "#c4b5fd", font_weight=700),
            text(152, 211, "Awaiting first traffic snapshot", 25, "#f8fafc", font_weight=700),
            text(152, 246, "The card will populate after the first rolling 14-day collection.", 15, "#9aa9c4"),
            '<rect x="152" y="276" width="161" height="24" rx="12" fill="#211b3e"/>',
            text(173, 293, "NO SNAPSHOT YET", 10, "#c4b5fd", font_weight=700, letter_spacing=1.4),
            text(64, 385, "Native GitHub repository traffic - Aggregate display only", 12, "#71809b"),
        )
    )
    return base_svg(content, "Awaiting first traffic snapshot")


def populated_svg(summary: dict) -> str:
    top = summary["top"]
    total_views = summary["total_views"]
    if top:
        share = top["views"] / total_views if total_views else 0
        top_name = shorten(top["name"])
        top_line = f'{number(top["views"])} views - {number(top["view_uniques"])} unique visitors'
        share_label = f"{share * 100:.1f}% of total views"
        share_width = max(0, min(972, round(972 * share)))
    else:
        top_name = "No available repository data"
        top_line = "The latest snapshot has no repositories with status ok."
        share_label = "No available view data"
        share_width = 0

    values = (
        number(total_views) if top else "-",
        number(summary["total_clones"]) if top else "-",
        number(summary["tracked"]),
        f'{summary["available"]} / {summary["tracked"]}',
    )
    content = "\n".join(
        (
            text(64, 66, "PORTFOLIO TRAFFIC", 14, "#c4b5fd", font_weight=700, letter_spacing=2.5),
            text(1036, 66, "ROLLING 14 DAYS", 12, "#93c5fd", font_weight=700, text_anchor="end", letter_spacing=1.8),
            text(64, 91, "GitHub repository activity", 16, "#94a3b8"),
            metric_card(64, "TOTAL VIEWS", values[0]),
            metric_card(314, "TOTAL CLONES", values[1]),
            metric_card(564, "TRACKED REPOS", values[2]),
            metric_card(814, "AVAILABLE", values[3]),
            text(64, 266, "TOP REPOSITORY BY VIEWS", 11, "#9aa9c4", font_weight=700, letter_spacing=1.7),
            text(64, 300, top_name, 23, "#f8fafc", font_weight=700),
            text(1036, 300, top_line, 14, "#a5b4fc", text_anchor="end"),
            text(64, 330, "Traffic share", 11, "#71809b"),
            text(1036, 330, share_label, 11, "#71809b", text_anchor="end"),
            '<rect x="64" y="343" width="972" height="12" rx="6" fill="#202b43"/>',
            f'<rect x="64" y="343" width="{share_width}" height="12" rx="6" fill="url(#bar)"/>',
            text(64, 394, f'Snapshot: {summary["snapshot_date"]}', 12, "#71809b"),
            text(1036, 394, "Native GitHub repository traffic", 12, "#71809b", text_anchor="end"),
        )
    )
    if top:
        description = (
            f'{number(total_views)} total views and {number(summary["total_clones"])} total clones '
            f'across {summary["available"]} of {summary["tracked"]} tracked repositories.'
        )
    else:
        description = (
            f'Latest snapshot has no available repository metrics across {summary["tracked"]} '
            "tracked repositories."
        )
    return base_svg(content, description)


def generate(input_path: Path, output_path: Path) -> None:
    data = load_data(input_path)
    snapshot = latest_snapshot(data)
    svg = placeholder_svg() if snapshot is None else populated_svg(summarize(snapshot))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        generate(args.input, args.output)
        print(f"Generated traffic card: {args.output}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"traffic card error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
