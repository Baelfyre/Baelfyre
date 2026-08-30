#!/usr/bin/env python3
"""Collect rolling GitHub repository traffic snapshots for the profile portfolio."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROFILE_STATUS = Path("profile-status.json")
OUTPUT = Path("analytics/repository-traffic.json")
API_VERSION = "2026-03-10"
MAX_SNAPSHOTS = 365


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def repository_list() -> list[str]:
    status = load_json(PROFILE_STATUS)
    projects = status.get("projects")
    if not isinstance(projects, list):
        raise ValueError("profile-status.json projects must be a list")

    repositories = [os.environ.get("GITHUB_REPOSITORY", "Baelfyre/Baelfyre")]
    for project in projects:
        repository = project.get("repository") if isinstance(project, dict) else None
        if isinstance(repository, str) and repository.strip():
            repositories.append(repository.strip())

    return list(dict.fromkeys(repositories))


def fetch_traffic(repository: str, metric: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{repository}/traffic/{metric}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "baelfyre-profile-traffic-collector",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def unavailable_status(status_code: int | None) -> dict:
    result = {"status": "unavailable"}
    if status_code is not None:
        result["http_status"] = status_code
    return result


def collect_repository(repository: str, token: str) -> dict:
    try:
        views = fetch_traffic(repository, "views", token)
        clones = fetch_traffic(repository, "clones", token)
    except HTTPError as exc:
        return unavailable_status(exc.code)
    except (URLError, TimeoutError):
        return unavailable_status(None)

    required = (
        views.get("count"),
        views.get("uniques"),
        clones.get("count"),
        clones.get("uniques"),
    )
    if not all(isinstance(value, int) and value >= 0 for value in required):
        return unavailable_status(None)

    return {
        "status": "ok",
        "views": {"count": views["count"], "uniques": views["uniques"]},
        "clones": {"count": clones["count"], "uniques": clones["uniques"]},
    }


def load_output() -> dict:
    if not OUTPUT.exists():
        return {
            "schema_version": "baelfyre.repository-traffic.v1",
            "source": "GitHub REST repository traffic API",
            "window": "rolling_14_days",
            "snapshots": [],
        }

    data = load_json(OUTPUT)
    if data.get("schema_version") != "baelfyre.repository-traffic.v1":
        raise ValueError("repository traffic schema_version drift")
    if data.get("window") != "rolling_14_days":
        raise ValueError("repository traffic window drift")
    if not isinstance(data.get("snapshots"), list):
        raise ValueError("repository traffic snapshots must be a list")
    return data


def validate() -> None:
    repositories = repository_list()
    if not repositories:
        raise ValueError("no repositories configured for traffic collection")
    if len(repositories) != len(set(repositories)):
        raise ValueError("duplicate repositories after normalization")
    if OUTPUT.exists():
        load_output()
    print(f"Traffic analytics configuration valid for {len(repositories)} repositories.")


def write_snapshot(token: str) -> dict:
    data = load_output()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot_date = now.date().isoformat()

    repositories = {
        repository: collect_repository(repository, token)
        for repository in repository_list()
    }

    snapshot = {
        "snapshot_date": snapshot_date,
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "repositories": repositories,
    }

    snapshots = [
        existing
        for existing in data["snapshots"]
        if existing.get("snapshot_date") != snapshot_date
    ]
    snapshots.append(snapshot)
    data["snapshots"] = snapshots[-MAX_SNAPSHOTS:]
    data["last_updated"] = snapshot["captured_at"]
    data["measurement_note"] = (
        "Each entry is a GitHub rolling 14-day repository snapshot. "
        "Unique counts must not be summed across repositories or snapshots."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    try:
        validate()
        if args.validate:
            return 0

        token = os.environ.get("TRAFFIC_READ_TOKEN", "").strip()
        if not token:
            raise ValueError("TRAFFIC_READ_TOKEN is required for collection")

        snapshot = write_snapshot(token)
        ok = sum(
            1
            for item in snapshot["repositories"].values()
            if item.get("status") == "ok"
        )
        total = len(snapshot["repositories"])
        print(f"Collected GitHub traffic for {ok}/{total} repositories.")
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"traffic analytics error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
