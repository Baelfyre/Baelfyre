# Repository Traffic Analytics

This profile repository can collect GitHub's native repository traffic metrics for the repositories listed in `profile-status.json`, plus `Baelfyre/Baelfyre` itself.

## What is collected

For each repository, the collector stores only the aggregate values GitHub reports for its rolling 14-day traffic window:

- repository views;
- unique repository visitors;
- repository clones; and
- unique repository cloners.

The collector does not store visitor identities, IP addresses, referrer domains, popular paths, or raw per-day traffic records. It also does not calculate a lifetime unique-visitor count because GitHub does not expose one through the repository traffic API.

Historical entries are snapshots of overlapping 14-day windows. Their unique counts must not be added together or treated as lifetime uniques.

## Required credential

Create a dedicated fine-grained personal access token named for traffic analytics and give it access only to the repositories whose traffic should be collected.

Required repository permission:

- Administration: Read-only

Add the token to the `Baelfyre/Baelfyre` repository as an Actions secret named:

`TRAFFIC_READ_TOKEN`

Do not reuse `PORTFOLIO_READ_TOKEN`. Keeping traffic access separate preserves least privilege and avoids coupling profile-content automation to repository-administration metadata access.

If the secret is absent, the scheduled workflow validates its configuration and exits successfully without collecting traffic.

## Storage and interpretation

Snapshots are stored in `analytics/repository-traffic.json`. The workflow keeps at most 365 daily snapshots and replaces a same-day snapshot when manually rerun.

The README profile-view badge is separate. It is an external image counter and must not be interpreted as GitHub-verified unique profile visitors.
