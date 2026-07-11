---
type: ADR
title: GitHub Actions CI
description: Read-only GitHub Actions workflow runs the offline suite on Python 3.12-3.14 and checks OKF mapping freshness on pull requests and main.
tags: [adr]
timestamp: 2026-07-11T17:05:35Z
status: accepted
---

# Status

Accepted by the owner on 2026-07-11.

# Context

Skywatch's canonical `make test` suite is fully offline and supports Python 3.12+, but it previously ran only on the owner's machine. The repository needs an independently reproducible check for pull requests and `main`, plus a trustworthy README test-status badge. CI introduces hosted infrastructure and maintained action dependencies, so the repository's decision policy requires this choice to be recorded.

# Decision

Use one GitHub Actions workflow at `.github/workflows/test.yml`, triggered by pull requests and pushes to `main`:

- Run `make test` on `ubuntu-latest` with Python 3.12, 3.13, and 3.14. These cover the supported floor, intermediate minor release, and development version named in ADR-0001.
- Run `bash scripts/okf check-stale` in a separate job, with `OKF_BASE` set to the pull request base SHA or the push event's previous SHA and full Git history available.
- Grant the workflow only `contents: read`; do not provide secrets or credentials, and do not publish, deploy, or send real mail.
- Use the official `actions/checkout` and `actions/setup-python` actions, pinned to their current major versions. Dependabot may later track the `github-actions` ecosystem without changing the application runtime.
- Link the README Tests badge directly to this workflow.

# Alternatives considered

- **Local tests only:** zero hosted configuration, but every contribution would rely on an unverifiable local result and the README could not report current test status.
- **Test only one Python version:** cheaper by a small amount, but it would leave the documented 3.12 floor or newer stdlib behavior unchecked. The suite has no package-install step, so the three-version matrix is inexpensive.
- **A third-party CI service:** could run the same commands, but adds another account and integration when the repository already lives on GitHub.
- **Run OKF once per Python matrix entry:** repeats a shell-and-git check whose result does not vary by Python version.

# Consequences

- Pull requests and `main` get clean-checkout test results across all supported Python minors.
- The OKF job catches mapped source changes that omit the governing document or a dated log rationale.
- The test badge reports a real workflow result rather than a static claim.
- CI now depends on GitHub-hosted runners and two official actions. Their major versions require maintenance even though Skywatch still has zero third-party runtime packages.
- The workflow filename and README badge URL must stay in sync.
- Passing CI remains a reported check until repository branch protection is separately configured to require it.

# Rollback / revisit trigger

Revisit if GitHub-hosted runner limits become material, a supported Python version cannot be provisioned reliably, the repository moves away from GitHub, or CI gains deployment, secrets, or other side effects. Rolling back means deleting the workflow and its Tests badge; application code and local verification remain unchanged.
