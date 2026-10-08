# Public repository traffic analytics

The GitHub profile publishes traffic only for repositories explicitly listed in
`analytics/public-traffic-sources.json`. The initial approved source is
`Baelfyre/Baelfyre` only. Being listed as a project in
`profile-status.json`, providing read credentials, or having public-facing
project descriptions never grants permission to publish traffic metrics.

## Publication boundary

- The allowlist is explicit and versioned.
- A project source must also be marked `auth: public` in the profile index;
  the profile repository itself is independently eligible.
- Collection rechecks each source's live GitHub public visibility before reading traffic.
- The collector rejects historical JSON containing an unapproved repository.
- The SVG generator, workflow summary, and pre-commit publication verifier each
  validate the public-only dataset.
- The repository currently publishes only the profile repository's approved
  rolling 14-day snapshots. Never copy private-source metrics, identities,
  source responses, or error details into publicly committed artifacts.

The traffic JSON and SVG are stored in a **public** repository. Any data committed
there, including past versions, may remain visible in Git history. Replacing
the current files does **not** erase historical exposure. History rewriting,
retention decisions, and credential changes require separately authorized review.

## Data and interpretation

Only aggregate rolling 14-day views, unique visitor counts, clones, and
unique cloners returned by GitHub are collected for approved public sources.
Snapshots overlap, so do not sum uniques across dates as lifetime counts.
The external README profile-view badge is not GitHub-verified unique traffic.

## Credentials and automation

The daily workflow uses a dedicated `TRAFFIC_READ_TOKEN` stored as a
GitHub Actions secret with only the necessary repository access and read-only
Administration permission. Do not reuse `PORTFOLIO_READ_TOKEN`.

Missing credentials skip collection without inventing data. Each run must pass
the public-policy validation, live visibility checks, SVG generator validation,
and final publication verifier before committing analytics changes.
