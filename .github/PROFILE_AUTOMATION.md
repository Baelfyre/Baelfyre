# Profile PIO Automation

The GitHub profile uses one deliberately small public-presentation contract per project:

```text
profile-pio.json
```

The profile updater reads only that file from each allowlisted repository. It does not infer public status from private trackers, repository README files, release indexes, branches, validation records, implementation prompts, or internal phase data.

## PIO contract

Every project PIO must contain exactly:

```json
{
  "schema_version": "1.0",
  "project": "Project Name",
  "featured": true,
  "summary": "Public-safe project summary.",
  "status": "Current public-safe state.",
  "next": "Current public-safe next direction.",
  "url": null
}
```

`url` may be `null` for a private project or an HTTPS public link.

The PIO is presentation authority only. Canonical project contracts, implementation state, governance, validation evidence, and continuity records remain authoritative inside their own repositories.

## Current project sources

The profile currently reads `profile-pio.json` from:

- `Baelfyre/Orderly`
- `Baelfyre/CritiQual`
- `Baelfyre/SchemaForge`
- `Baelfyre/Orchestra`
- `Baelfyre/hivemind-pathway-assessment`
- `Baelfyre/HiveMind_1.0`

Orchestra is public. The other project repositories are private.

## Generated README blocks

The updater owns two README regions:

```text
<!-- FEATURED_PROJECTS:START -->
<!-- FEATURED_PROJECTS:END -->
```

and:

```text
<!-- PROJECT_STATUS:START -->
<!-- PROJECT_STATUS:END -->
```

The two blocks intentionally serve different editorial roles while sharing the same PIO source:

- Featured Projects renders only `project`, `summary`, and optional `url`, so it explains what problem each system exists to solve.
- Current Project Status renders `status` and `next`, so implementation progress is reported once instead of duplicated in the narrative section.

Featured Projects must appear before the Tech Stack section so the profile demonstrates systems work before listing tools.

Capstone Research remains in the dedicated Research & Capstone section rather than the generated implementation-project table.

## Private repository access

The Actions secret is:

```text
PORTFOLIO_READ_TOKEN
```

For the PIO architecture, that token should have read-only Contents access only to the private repositories whose PIOs the profile must read.

GitHub fine-grained repository permissions are repository-scoped rather than file-scoped, so the credential cannot technically be limited to one file. The updater itself is stricter: it only requests the allowlisted `profile-pio.json` path.

Do not grant write access and do not grant access to unrelated repositories.

Authentication behavior is fail-safe but not silent:

- If the token is not configured, private sources use the last validated public-safe fallback stored in `profile-status.json`.
- If a token is configured and GitHub rejects it with HTTP 401 or 403, the workflow fails. A bad or unauthorized credential must not appear as a healthy profile refresh.
- Other temporary source failures keep the validated fallback and emit a warning.

## Refresh behavior

`.github/workflows/update-profile.yml` runs:

- manually through `workflow_dispatch`;
- every six hours;
- on `repository_dispatch` with event type `project-status-changed`;
- when profile automation files change.

A project may optionally request an immediate refresh with:

```json
{
  "event_type": "project-status-changed"
}
```

The dispatch event carries no profile content and grants no authority. It only triggers a fresh read of the allowlisted PIO sources.

## Maintenance rule

A project's `profile-pio.json` must be reconciled whenever a canonical change materially affects:

- public project summary;
- current public status;
- next public direction;
- Featured Project visibility;
- public project URL.

Ordinary implementation changes that do not alter those public fields do not require meaningless PIO churn.

## Public-safety boundary

The profile generator must not publish or consume as presentation authority:

- raw private tracker records;
- security findings or vulnerability details;
- validation logs or evidence digests;
- private branch names or commit/tree SHAs;
- local filesystem paths;
- implementation prompts;
- provider configuration;
- secrets, tokens, or credentials;
- arbitrary private repository metadata.

Adding a project requires an explicit `profile-status.json` allowlist entry and a valid project-side `profile-pio.json`.
