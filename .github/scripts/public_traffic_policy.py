#!/usr/bin/env python3
"""Fail-closed rules for publishing repository traffic from a public profile."""

from __future__ import annotations

import json
import re
from pathlib import Path

POLICY_PATH = Path("analytics/public-traffic-sources.json")
PROFILE_STATUS_PATH = Path("profile-status.json")
PROFILE_REPOSITORY = "Baelfyre/Baelfyre"
POLICY_SCHEMA = "baelfyre.public-traffic-sources.v1"
TRAFFIC_SCHEMA = "baelfyre.repository-traffic.v1"
REPOSITORY_PATTERN = re.compile(r"^Baelfyre/[A-Za-z0-9_.-]+$")


def load_publication_policy() -> tuple[str, ...]:
    """Only explicitly approved and public-configured sources are publishable."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    status = json.loads(PROFILE_STATUS_PATH.read_text(encoding="utf-8"))
    if set(policy) != {"schema_version", "repositories"}:
        raise ValueError("public traffic policy fields must match its contract")
    if policy["schema_version"] != POLICY_SCHEMA:
        raise ValueError("public traffic policy schema drift")
    sources = policy["repositories"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("public traffic allowlist must be non-empty")
    if not all(isinstance(item, str) and REPOSITORY_PATTERN.fullmatch(item) for item in sources):
        raise ValueError("public traffic allowlist has an invalid repository entry")
    if len(sources) != len(set(sources)):
        raise ValueError("public traffic allowlist contains duplicates")
    projects = status.get("projects")
    if not isinstance(projects, list):
        raise ValueError("profile project index is invalid")
    public_sources = {
        item["repository"] for item in projects
        if isinstance(item, dict)
        and isinstance(item.get("repository"), str)
        and item.get("auth") == "public"
    }
    public_sources.add(PROFILE_REPOSITORY)
    if not set(sources).issubset(public_sources):
        raise ValueError("public traffic source is not authorized as public")
    return tuple(sources)


def validate_published_dataset(data: dict, permitted: tuple[str, ...]) -> None:
    """Reject private or unapproved data anywhere in committed snapshot history."""
    if not isinstance(data, dict) or data.get("schema_version") != TRAFFIC_SCHEMA:
        raise ValueError("repository traffic schema drift")
    if data.get("window") != "rolling_14_days":
        raise ValueError("repository traffic window drift")
    snapshots = data.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("repository traffic snapshots must be a list")
    allowed = set(permitted)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            raise ValueError("repository traffic snapshot must be an object")
        repositories = snapshot.get("repositories")
        if not isinstance(repositories, dict):
            raise ValueError("repository traffic repositories must be an object")
        if not set(repositories).issubset(allowed):
            raise ValueError("unapproved repository data in public traffic snapshots")
