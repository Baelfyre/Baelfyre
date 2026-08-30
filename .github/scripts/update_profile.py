#!/usr/bin/env python3
"""Refresh the GitHub profile from bounded per-project PIO contracts.

Each configured repository exposes exactly one public-presentation object at
`profile-pio.json`. The profile updater reads only that allowlisted file and
never interprets private trackers, README state, release indexes, validation
evidence, branches, or internal phase records.

If the private token is not configured, the updater preserves the last
validated public-safe fallback stored in profile-status.json. If a private
token is configured but GitHub returns HTTP 401, 403, or 404 for a private
PIO, the refresh fails visibly so invalid credentials or inaccessible private
repositories cannot masquerade as a healthy sync.
"""

from __future__ import annotations

import base64
import html
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

PIO_KEYS = {
    "schema_version",
    "project",
    "featured",
    "summary",
    "status",
    "next",
    "url",
}


def _headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Baelfyre-profile-pio-updater",
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


def _validate_pio(pio: dict[str, Any], expected_project: str) -> None:
    if set(pio) != PIO_KEYS:
        raise ValueError(f"{expected_project} PIO field contract mismatch")
    if pio.get("schema_version") != "1.0":
        raise ValueError(f"{expected_project} PIO schema_version mismatch")
    if pio.get("project") != expected_project:
        raise ValueError(f"{expected_project} PIO project identity mismatch")
    if not isinstance(pio.get("featured"), bool):
        raise ValueError(f"{expected_project} PIO featured must be boolean")
    for key in ("summary", "status", "next"):
        value = pio.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{expected_project} PIO {key} must be non-empty text")
    url = pio.get("url")
    if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
        raise ValueError(f"{expected_project} PIO url must be null or HTTPS")


def _token_for(project: dict[str, Any]) -> str:
    auth = project.get("auth")
    if auth == "public":
        return PUBLIC_TOKEN
    if auth == "private":
        if not PRIVATE_TOKEN:
            raise PermissionError("PORTFOLIO_READ_TOKEN is not configured")
        return PRIVATE_TOKEN
    raise ValueError(f"unknown auth mode: {auth}")


def _refresh_projects(status: dict[str, Any]) -> None:
    projects = status.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ValueError("profile-status projects must be a non-empty list")

    for project in projects:
        if not isinstance(project, dict):
            raise ValueError("profile-status project entries must be objects")
        repository = project.get("repository")
        path = project.get("path")
        fallback = project.get("fallback")
        if not isinstance(repository, str) or not repository:
            raise ValueError("profile-status project missing repository")
        if path != "profile-pio.json":
            raise ValueError(f"{repository} must use profile-pio.json")
        if project.get("authority") != "public_presentation_only":
            raise ValueError(f"{repository} PIO authority must remain presentation-only")
        if not isinstance(fallback, dict):
            raise ValueError(f"{repository} missing public-safe fallback")

        expected_project = fallback.get("project")
        if not isinstance(expected_project, str) or not expected_project:
            raise ValueError(f"{repository} fallback missing project identity")
        _validate_pio(fallback, expected_project)

        try:
            token = _token_for(project)
            pio = _fetch_repo_json(repository, path, token=token)
            _validate_pio(pio, expected_project)
        except urllib.error.HTTPError as exc:
            if project.get("auth") == "private" and PRIVATE_TOKEN and exc.code in (401, 403, 404):
                raise RuntimeError(
                    f"{expected_project} private PIO access failed with HTTP {exc.code}; "
                    "PORTFOLIO_READ_TOKEN is configured but cannot access the allowlisted repository/path"
                ) from exc
            print(
                f"warning: {expected_project} PIO unavailable; keeping fallback: {exc}",
                file=sys.stderr,
            )
            continue
        except (
            PermissionError,
            urllib.error.URLError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"warning: {expected_project} PIO unavailable; keeping fallback: {exc}",
                file=sys.stderr,
            )
            continue

        project["fallback"] = pio


def _render_project_name(pio: dict[str, Any]) -> str:
    name = str(pio["project"])
    url = pio.get("url")
    if isinstance(url, str) and url:
        return f"[{name}]({url})"
    return name


def _render_feature_title(pio: dict[str, Any]) -> str:
    name = html.escape(str(pio["project"]))
    url = pio.get("url")
    if isinstance(url, str) and url.startswith("https://"):
        return f'<strong><a href="{html.escape(url, quote=True)}">{name}</a></strong>'
    return f"<strong>{name}</strong>"


def _render_featured_projects(status: dict[str, Any]) -> str:
    cards: list[tuple[str, str]] = []
    for project in status["projects"]:
        pio = project["fallback"]
        if pio.get("featured") is not True:
            continue
        cards.append(
            (
                _render_feature_title(pio),
                html.escape(str(pio["summary"])),
            )
        )

    lines = ["<table>"]
    for index in range(0, len(cards), 2):
        row = cards[index : index + 2]
        lines.append("<tr>")
        for title, summary in row:
            lines.extend(
                [
                    '  <td width="50%" valign="top">',
                    f"    {title}<br>",
                    f"    <sub>{summary}</sub>",
                    "  </td>",
                ]
            )
        if len(row) == 1:
            lines.append('  <td width="50%" valign="top"></td>')
        lines.append("</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _render_status_table(status: dict[str, Any]) -> str:
    lines = [
        "| Project | Current State | Next Direction |",
        "| --- | --- | --- |",
    ]
    for project in status["projects"]:
        pio = project["fallback"]
        lines.append(
            "| "
            + " | ".join(
                [
                    _render_project_name(pio),
                    str(pio["status"]).replace("|", r"\|"),
                    str(pio["next"]).replace("|", r"\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _replace_block(readme: str, start: str, end: str, body: str) -> str:
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise RuntimeError(f"README markers must each appear exactly once: {start} / {end}")
    if readme.index(start) >= readme.index(end):
        raise RuntimeError(f"README markers are out of order: {start} / {end}")
    before, remainder = readme.split(start, 1)
    _, after = remainder.split(end, 1)
    return f"{before}{start}\n{body}\n{end}{after}"


def main() -> int:
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    readme = README_PATH.read_text(encoding="utf-8")

    _refresh_projects(status)

    blocks = status.get("generated_blocks", {})
    featured = blocks.get("featured_projects", {})
    project_status = blocks.get("project_status", {})

    readme = _replace_block(
        readme,
        featured["start_marker"],
        featured["end_marker"],
        _render_featured_projects(status),
    )
    readme = _replace_block(
        readme,
        project_status["start_marker"],
        project_status["end_marker"],
        _render_status_table(status),
    )

    STATUS_PATH.write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(readme, encoding="utf-8")
    print("Profile PIO refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
