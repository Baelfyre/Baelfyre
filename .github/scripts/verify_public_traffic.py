#!/usr/bin/env python3
"""Validate public analytics and their generated SVG before committing outputs."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from public_traffic_policy import load_publication_policy, validate_published_dataset, PROFILE_STATUS_PATH

TRAFFIC_PATH = Path("analytics/repository-traffic.json")
CARD_PATH = Path("assets/profile/portfolio-traffic-card.svg")


def verify() -> None:
    permitted = load_publication_policy()
    data = json.loads(TRAFFIC_PATH.read_text(encoding="utf-8"))
    validate_published_dataset(data, permitted)
    svg = CARD_PATH.read_text(encoding="utf-8")
    ET.fromstring(svg)
    status = json.loads(PROFILE_STATUS_PATH.read_text(encoding="utf-8"))
    for project in status.get("projects", []):
        repo = project.get("repository")
        if isinstance(repo, str) and repo not in permitted:
            if repo in svg:
                raise ValueError("unapproved repository identity in public traffic SVG")
            if len(repo) > 42 and f"{repo[:39]}..." in svg:
                raise ValueError("unapproved repository identity in public traffic SVG")
    if not svg.strip():
        raise ValueError("public traffic SVG must not be empty")
    print("Public traffic dataset and SVG passed publication-boundary validation.")


if __name__ == "__main__":
    verify()
