# Profile Status Automation

The GitHub profile README contains one generated project-status block bounded by:

```text
<!-- PROJECT_STATUS:START -->
<!-- PROJECT_STATUS:END -->
```

Only `.github/scripts/update_profile.py` should rewrite content inside that block.

## Sources

The updater is deliberately allowlisted.

1. `Baelfyre/Orchestra/README.json`
   - Public source.
   - Used only for public release state and whether `main` contains post-release work.

2. `Baelfyre/Padayon/padayon/generated/portfolio.json`
   - Private source.
   - Optional.
   - Used only for approved human-readable status mappings for Orderly, SchemaForge, Pathway, and HiveMind Workspace.
   - Raw private tracker fields are not copied to the public README.

If a source is unavailable, the updater preserves the last approved public-safe fallback in `profile-status.json`.

## Workflow

`.github/workflows/update-profile.yml` runs:

- manually through `workflow_dispatch`;
- every six hours;
- on `repository_dispatch` with event type `project-status-changed`.

The workflow commits only when the rendered public status actually changes. Routine checks with no meaningful status change create no commit.

## Private repository access

To enable refreshes from Padayon, configure a repository Actions secret named:

```text
PORTFOLIO_READ_TOKEN
```

Use a fine-grained GitHub token with the minimum required access:

- repository: `Baelfyre/Padayon`;
- permission: Contents, read-only.

Do not grant write access to Padayon and do not grant access to unrelated repositories.

If the secret is not configured, the workflow still refreshes public Orchestra release state and preserves the approved private-project fallback statuses.

## Cross-repository immediate refresh

The scheduled workflow is the default synchronization mechanism. A repository may optionally request an immediate refresh by sending a `repository_dispatch` event to `Baelfyre/Baelfyre` with:

```json
{
  "event_type": "project-status-changed"
}
```

The credential used to send that event should be narrowly scoped to the profile repository. A dispatch event only triggers the updater. It does not supply public README content or bypass the allowlisted sources.

## Public-safety boundary

The profile generator must not publish:

- raw private tracker records;
- security findings or vulnerability details;
- validation logs or evidence digests;
- private branch names or local filesystem paths;
- secrets, tokens, credentials, or provider configuration;
- arbitrary commit messages from private repositories.

New project sources or fields require an explicit code change to the updater.
