#!/usr/bin/env python3
"""Refresh the bounded live-project status block in the GitHub profile README.

The updater intentionally reads only allowlisted machine-readable sources:
- Baelfyre/Orchestra/README.json for public release state.
- Baelfyre/Padayon/padayon/generated/portfolio.json for private project continuity,
  but only when PORTFOLIO_READ_TOKEN is configured.

If the private token is unavailable or a source cannot be read, the updater keeps
the last approved public-safe fallback already stored in profile-status.json.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
README_PATH = ROOT / "README.md"
STATUS_PATH = ROOT / "profile-status.json"

GITHUB_API = "https://api.github.com"
PUBLIC_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
PRIVATE_TOKEN = os.environ.get("PORTFOLIO_READ_TOKEN", "").strip()

PADAYON_ID_MAP = {
    "orderly": "orderly",
    "schemaforge": "schemaforge",
    "pathway": "pathway",
    "hivemind-workspace": "hivemind-workspace",
}


def _headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Baelfyre-profile-status-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str, token: str = "") -> Any:
    request = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _fetch_repo_json(repository: str, path: str, token: str = "") -> dict[str, Any]:
    encoded_path = urllib.parse.quote(path, safe="/")
    payload = _get_json(
        f"{GITHUB_API}/repos/{repository}/contents/{encoded_path}",
        token=token,
    )
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError(f"{repository}/{path} did not return file content")
    decoded = base64.b64decode(content).decode("utf-8")
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError(f"{repository}/{path} is not a JSON object")
    return data


def _project_by_id(status: dict[str, Any], project_id: str) -> dict[str, Any]:
    for project in status["projects"]:
        if project["id"] == project_id:
            return project
    raise KeyError(project_id)


def _refresh_orchestra(status: dict[str, Any]) -> None:
    try:
        source = _fetch_repo_json(
            "Baelfyre/Orchestra",
            "README.json",
            token=PUBLIC_TOKEN,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"warning: Orchestra source unavailable; keeping fallback: {exc}", file=sys.stderr)
        return

    repository = source.get("repository", {})
    if not isinstance(repository, dict):
        return

    release = repository.get("current_public_release")
    post_release = repository.get("main_contains_post_release_work")

    if isinstance(release, str) and release:
        current = f"{release} published"
        if post_release is True:
            current += " · post-release work on main"
        _project_by_id(status, "orchestra")["current_state"] = current


def _humanize_padayon(project_id: str, source: dict[str, Any]) -> tuple[str, str] | None:
    phase = str(source.get("current_phase", ""))
    source_status = str(source.get("status", ""))

    if project_id == "orderly" and phase == "FBR1":
        return (
            "FBR0 verified · FBR1 authorized, not started",
            "Firebase identity and platform foundation",
        )

    if project_id == "schemaforge" and phase == "L1":
        return (
            "Frontend F5 merged and verified",
            "L1 integrated local bundle",
        )

    if project_id == "pathway":
        if "POST_C2_SECURITY_AUDIT_GATE" in phase or "SECURITY_AUDIT_GATE_ACTIVE" in source_status:
            return (
                "C2 complete · post-C2 security audit gate active",
                "Complete the security gate before later-phase advancement",
            )

    if project_id == "hivemind-workspace":
        if "DEFERRED" in phase or "DEFERRED" in source_status:
            return (
                "Deferred · not active priority",
                "Reassess after the Orderly capstone",
            )

    return None


def _refresh_private_portfolio(status: dict[str, Any]) -> None:
    if not PRIVATE_TOKEN:
        print(
            "notice: PORTFOLIO_READ_TOKEN is not configured; "
            "keeping approved private-project fallbacks",
            file=sys.stderr,
        )
        return

    try:
        portfolio = _fetch_repo_json(
            "Baelfyre/Padayon",
            "padayon/generated/portfolio.json",
            token=PRIVATE_TOKEN,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"warning: Padayon source unavailable; keeping fallbacks: {exc}", file=sys.stderr)
        return

    entries = portfolio.get("projects", [])
    if not isinstance(entries, list):
        return

    by_id = {
        str(item.get("project_id")): item
        for item in entries
        if isinstance(item, dict) and item.get("project_id")
    }

    for profile_id, padayon_id in PADAYON_ID_MAP.items():
        source = by_id.get(padayon_id)
        if not source:
            continue
        display = _humanize_padayon(profile_id, source)
        if not display:
            continue
        current_state, next_direction = display
        project = _project_by_id(status, profile_id)
        project["current_state"] = current_state
        project["next_direction"] = next_direction


def _render_project_name(project: dict[str, Any]) -> str:
    name = str(project["name"])
    url = project.get("url")
    if isinstance(url, str) and url:
        return f"[{name}]({url})"
    return name


def _render_table(status: dict[str, Any]) -> str:
    lines = [
        "| Project | Current State | Next Direction |",
        "| --- | --- | --- |",
    ]
    for project in status["projects"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _render_project_name(project),
                    str(project["current_state"]).replace("|", r"\|"),
                    str(project["next_direction"]).replace("|", r"\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _replace_generated_block(readme: str, status: dict[str, Any]) -> str:
    generated = status["generated_block"]
    start = generated["start_marker"]
    end = generated["end_marker"]

    if start not in readme or end not in readme:
        raise RuntimeError("README project-status markers are missing")

    before, remainder = readme.split(start, 1)
    _, after = remainder.split(end, 1)
    return f"{before}{start}\n{_render_table(status)}\n{end}{after}"


def main() -> int:
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    readme = README_PATH.read_text(encoding="utf-8")

    _refresh_orchestra(status)
    _refresh_private_portfolio(status)

    rendered = _replace_generated_block(readme, status)

    STATUS_PATH.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(rendered, encoding="utf-8")

    print("Profile project status refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
