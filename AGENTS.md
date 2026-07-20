---
type: Playbook
title: Codex repo instructions
description: Master objective, grounding rules, and workflow for Codex in this repository.
tags: [Codex, agent-instructions, adr, specs]
timestamp: 2026-07-19T00:00:00Z
owner: "Lila Brooks"
deciders: ["Lila Brooks"]
---

<!-- Template. Fill every [bracket], update the timestamp, then delete this comment.
     Claude Code ignores the frontmatter; it exists to make this file a valid OKF
     concept (type is the only required field, per OKF v0.1). -->

# Master objective

Current state: v1 is built and the goal was met on 2026-07-11 — scheduler, both upstream sources, verdict join, SMTP digest, status page, and a clean-checkout README quickstart, all verified (see `docs/log.md`). ADRs 0001–0004 were accepted by the owner on 2026-07-19 (0005 was already accepted) and bind future work; new milestones enter `docs/GOAL.md` only by owner decision. Skywatch: a local always-on service that emails a digest when tonight's ISS pass is worth stepping outside for.

Target state: A scheduler fetching ISS passes and cloud cover for a configured location into SQLite, joining them into go/maybe/skip verdicts, serving a local status page, and sending an SMTP digest only when tonight has a watchable pass — all testable fully offline.

Constraints: Follow `docs/GOAL.md`, the specs in `docs/specs/` as they land, and all accepted ADRs in `docs/adr/`. Stack and tooling choices are delegated to proposed ADRs. External data via public HTTP APIs only; secrets via environment only; real sends owner-gated.

Done when: `make test` passes offline, `make run` serves the status page locally, every milestone in `docs/GOAL.md` is checked with its verification, and `git check-ignore .env` succeeds.

# Session-start context

Codex does not resolve `@` imports, so read these three small files at the start of every session — they carry the goal and the knowledge indexes. Full specs and ADRs stay on disk until a task needs them.

- `docs/GOAL.md`
- `docs/specs/index.md`
- `docs/adr/index.md`

# Goal iteration

`docs/GOAL.md` defines what this repo is for: the kind of deliverable (app, service, or utility), the problem, the target state, success criteria, and an ordered milestone backlog. The Master objective above is its one-screen summary; keep the two consistent, with `docs/GOAL.md` carrying the detail.

- `docs/GOAL.md` is part of the session-start reads above, so the goal is in context from the first task. Re-read it during a session only after it changes.
- When asked to continue or iterate without a specific task, take the first unchecked milestone and run it through the task workflow below. When its verification passes, check it off, log it, and continue with the next unchecked milestone. Stop when the backlog is empty, a decision reserved for me comes up, or I say stop.
- Resuming after an interruption: at session start, if the working tree holds uncommitted changes, treat them as in-flight work from a cut-off session, not a clean slate. Reconcile them against the first unchecked milestone and the newest `docs/log.md` entry, then finish that work or back it out before taking a new milestone.
- Check a milestone off only when its stated verification passes, then add a dated `docs/log.md` entry.
- Before reporting the goal met, run the acceptance pass (the `okf-acceptance-pass` skill carries the full checklist): exercise the deliverable as a first-time user — clean checkout, README quickstart, the goal's example interactions plus obvious variants and wrong inputs. Tests prove the contract; this pass proves the experience. Fix in-scope breakage before declaring the goal met, record what was exercised in `docs/log.md`, and carry out-of-scope findings into the candidate milestones below.
- When every milestone is checked, the success criteria pass, and the acceptance pass is clean, report that the goal is met and stop building. List any ADRs still `status: proposed` in that report (`bash scripts/okf pending`) so I can review them. Then offer candidate next milestones for me to choose from: known items in `docs/log.md`, revisit triggers in accepted ADRs, findings from the acceptance pass, standard repo hygiene the repo still lacks (a license, CI that runs the Verification commands and `bash scripts/okf check-stale` on pushes and pull requests, dependency-update automation, README badges), and extensions that fit the stated non-goals — with options that would first need me to revise a non-goal listed separately. Proposing is not adding: nothing enters `docs/GOAL.md` without my confirmation, and at my direction you draft the chosen milestones with their verifications.
- When the code and the goal disagree, flag it. Changing `docs/GOAL.md` (scope, success criteria, milestone order) is my decision.
- If `docs/GOAL.md` is missing, create it with these sections before the first milestone task: Goal (kind, problem, solution), Target state, Success criteria, Non-goals, Constraints, Milestones. If it, or this file, is missing content or still contains unfilled template brackets, run the goal interview below before iterating.

# Goal interview

When `docs/GOAL.md` or this file still needs filling, run the goal interview with me before iterating — a few questions at a time, drafting as you go, instead of asking me to edit templates. The `okf-goal-interview` skill carries the full script with worked examples; without it, ask in order: (1) what is being built and for whom → Kind and Problem; (2) the concrete done state → Target state; (3) 2-3 example interactions with the primary interface, including at least one messy or wrong one, phrased per repo kind → spec examples and test cases; (4) the mechanical verification → Success criteria and Verification commands — a new repo's first milestone establishes the canonical commands (conventionally `make test` and `make run`), and any tool a verification step names beyond the repo's own stack gets confirmed installed or marked owner-gated so the loop expects the pause; (5) non-goals; (6) which stack choices are fixed versus decided later through proposed ADRs → Constraints; (7) the first shippable slice → the first milestone. Push back on answers that can't be checked mechanically; in an existing codebase propose answers from the code first and let me correct them; draft the backlog to end with a README-quickstart milestone by default (I can drop it); confirm the finished `docs/GOAL.md` with me before starting the loop. Manual editing stays a valid alternative; never overwrite goal content I wrote by hand.

# Docs bootstrap

If `/docs/specs` or `/docs/adr` doesn't exist yet, create this structure before the first task. The session-start reads above assume this structure exists; creating it fixes that from the next session on:

Installer note: when setting up a repo from outside Codex, prefer `bash scripts/create-new-repo <target>` for empty repos or `bash scripts/update-existing-repo <target>` for existing repos. This bootstrap section is the in-session fallback when those scripts were not used.

Adopting an existing codebase goes beyond bootstrap: after the updater runs, work through the adoption pass with me (the `okf-adopt` skill carries the full sequence) — inventory the existing knowledge without moving anything, populate `docs/okf-map.yml` so `check-stale` becomes the authority, backfill missing specs from `bash scripts/okf draft` output promoted per this repo's own conventions and validators, and validate end to end before the loop starts. Migrating this repo's layout or naming to the kit's defaults happens only at my direction, never by default.

```
docs/
├── index.md        # bundle root: declares okf_version, links the bundle files
├── GOAL.md         # goal, success criteria, milestone backlog (see Goal iteration)
├── log.md          # dated changelog, newest first
├── okf-map.yml     # maps source paths to governing specs/ADRs
├── specs/
│   ├── index.md    # lists each spec with a one-line description
│   └── _drafts/    # generated spec drafts; review before promoting
└── adr/
    └── index.md    # lists each ADR with a one-line description
```

`docs/index.md` starts with a frontmatter block declaring the OKF version (the bundle root is the only `index.md` allowed frontmatter):

```yaml
---
okf_version: "0.1"
---
```

Every new spec or ADR file gets YAML frontmatter with at least a `type:` field (OKF v0.1), plus `title` and `description`. Keep each `index.md` current when files are added or renamed.

`docs/okf-map.yml` maps source globs to the specs and ADRs that govern them. Keep it current when modules move or new source areas get their own contracts.

Brownfield alternative: a repo that already keeps its specs or ADRs elsewhere points the kit at them with an optional `layout:` block in `docs/okf-map.yml` (keys `specs_dir`, `adr_dir`, `stamp_file`; defaults match the tree above). The helper, hooks, and installers all follow it — never relocate existing knowledge just to satisfy the default tree. Mapped governing docs may also be machine-readable contracts (JSON Schemas, OpenAPI) living outside `/docs`.

# Agent config (committed to the repo)

- `.codex/hooks.json` — wires the guardrail hooks for Codex: `check-okf-version.sh` at SessionStart, `check-docs-sync.sh` at Stop, both invoked via `bash` so no executable bit is needed. Committed.
- `.claude/skills/okf-*/SKILL.md` — kit-installed workflow skills (goal interview, acceptance pass, ADR review, kit upgrade, adoption pass, second-agent port) for Claude Code sessions. Committed. Codex does not load skills, so in Codex sessions the resident one-liners in this file always bind on their own.
- `.codex/hooks/check-docs-sync.sh` — Stop hook. Committed. Don't move, rename, or disable it; if it blocks a stop, do the doc update it asks for. Kept byte-identical to `.claude/hooks/check-docs-sync.sh`: when one copy changes, sync the other.
- `.codex/hooks/check-okf-version.sh` — SessionStart hook. Committed. Reports OKF spec version drift; act per the OKF version policy above. Kept byte-identical to the `.claude` copy.
- `scripts/okf` — repo-local OKF helper command. Committed. Use it for stale mapping checks, spec drafts, and ADR suggestions.
- `docs/okf-map.yml` — source-to-knowledge mapping used by `scripts/okf check-stale`. Committed.
- `.claude/settings.local.json` — personal overrides only. Never commit it.
- `CLAUDE.local.md` — personal per-repo memory. Never commit it.
- This repo is also worked on by Claude Code (`CLAUDE.md`, `.claude/`). The two playbooks describe the same workflow; when workflow text changes in one, mirror it in the other.

This playbook is itself the guided second-agent port the kit's `okf-second-agent` skill describes (the `.claude/skills/` copy carries the full procedure). The binding rules: session-start reads replace `@` imports (Codex resolves none); guardrails that are mechanical only in Claude Code are stated honestly as policy here; the hook copies under `.codex/hooks/` stay byte-identical to `.claude/hooks/` and are declared in the top-level `mirrors:` list in `docs/okf-map.yml` so the safe updater syncs them on kit upgrades; and the parity check lives in this repo's own test gate.

During bootstrap, ensure `.gitignore` contains these entries (the same set the installers append and `verify-install` requires — `!.env.example` keeps the sample env file trackable):

```
.claude/settings.local.json
CLAUDE.local.md
.okf-kit-backups/
.DS_Store
.env
.env.*
!.env.example
```

When the stack is chosen (typically the first milestone), also append its standard ignores — virtualenv or dependency directories, build output, caches, bytecode — before those files first appear in the working tree.

Everything else agent-related is committed: `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.codex/`, `scripts/okf`, and all of `/docs`.

# OKF version policy

A SessionStart hook compares `okf_version` in `docs/index.md` against the latest spec version on the official OKF repo. When it reports drift:

1. Read the current spec at https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md and identify what changed.
2. Minor bump (e.g. 0.1 → 0.2): backward-compatible. Migrate automatically, before the first task of the session: update `okf_version` in `docs/index.md`, apply any new formatting or structural conventions across `/docs`, log the migration in `/docs/log.md`. No approval needed.
3. Major bump (e.g. 0.x → 1.0): may contain breaking changes. Stop and present me a migration summary before changing any `/docs` files.

Never modify spec or ADR content as part of a version migration; only formatting, frontmatter, and structure.

# Kit version policy

The same SessionStart hook also compares `kit_version` in `docs/index.md` — stamped by the kit installers — against the kit's published `VERSION` on the source kit's main branch. When it reports drift, tell me and recommend the safe updater, `scripts/update-existing-repo` from an up-to-date kit clone (the `okf-kit-upgrade` skill carries the walkthrough): it refreshes provably unedited kit files in place after a backup and writes same-folder numbered candidates for everything else; reviewing candidates is my decision. If `docs/index.md` carries no `kit_version`, the hook stays silent and this policy is inactive.

The same hook also reports numbered kit candidates (`CLAUDE.2.md` and similar) still unresolved from an install or upgrade. They are inactive review copies no agent loads: remind me to merge what I want into the live files and delete each candidate rather than resolving them yourself, and never commit one unresolved.

# OKF helper commands

`scripts/okf` is a repo-local Bash helper installed by this kit. It is not an official OKF CLI, not a global command, and not a prompt. Always run it with `bash scripts/okf ...` unless this repo intentionally wraps it another way. The knowledge paths named below are the defaults; when `docs/okf-map.yml` carries a `layout:` block, every command follows it instead, and `new-adr` follows whatever ADR numbering already exists.

These commands are the deterministic path: prefer them over re-deriving numbering, index entries, or staleness by hand — the mechanics are computed in code so your judgment and context go to the content of the work. When a helper declines or misfires on this repo's conventions, do the workaround in the open and record it in a dated `docs/log.md` entry so the friction can be carried back into the kit; never quietly improvise the mechanics a helper exists for.

- `bash scripts/okf check-stale` — run after changing source files. If it reports stale mappings, update the mapped spec/ADR or add a dated `/docs/log.md` rationale explaining why no knowledge file changed. It also lists changed files with no mapping — non-blocking; add mappings as those areas gain their governing docs.
- `bash scripts/okf draft [paths...]` — generate fact-based drafts under `/docs/specs/_drafts/`. Most useful in existing codebases with undocumented modules. Treat drafts as scaffolding: verify them, rewrite them into human-readable commitments, then move promoted specs into `/docs/specs/` and update `/docs/specs/index.md`.
- `bash scripts/okf adr-suggest` — run when a change may include an architecture decision. Create a new ADR only when the suggestion points to a real decision: dependency, persistence, cache/queue/worker, auth/security/privacy, API contract, deployment, or ownership boundary.
- `bash scripts/okf new-adr <slug> [title]` — scaffold the next-numbered ADR in `/docs/adr/` with `status: proposed` frontmatter, the required sections, and an index entry. The scaffold is a skeleton, not a decision: fill every bracket before implementing against it.
- `bash scripts/okf new-spec <slug> [title]` — scaffold a spec in `/docs/specs/` with an index entry, then fill it in and map the governed source in `docs/okf-map.yml`.
- `bash scripts/okf pending` — list ADRs still `status: proposed`, plus any missing a status field. Run it when reporting the goal met, and whenever I ask what's awaiting my review.

# Grounding rules (docs are the source of truth)

- The spec and ADR indexes are preloaded by the imports above. Before planning any change, read the specific spec or ADR governing the files you'll touch.
- When code and docs disagree, flag the mismatch. Don't silently pick a side.
- If a task conflicts with an accepted ADR, stop and ask before writing code. Superseding an accepted ADR is my decision, made via a new ADR file.
- Architectural changes start with a new ADR in `/docs/adr/`, written per the decision policy below, before any implementation.

# Decision policy (I own the goal, you drive the decisions)

I provide the goal, constraints, and guardrails; you make the decisions that reach the goal and record them where I can review them.

- Implementation choices that stay inside existing specs, accepted ADRs, and the guardrails below are yours to make without asking.
- Decision-shaped changes — dependency, persistence, cache/queue/worker, auth/security/privacy, API contract, deployment, ownership boundary — start with a new ADR marked `status: proposed` in its frontmatter (scaffold it with `bash scripts/okf new-adr <slug> "Title"`), covering context, decision, alternatives considered, consequences, and a rollback or revisit trigger. Implement against the proposed ADR, then flag it in your summary and in `docs/log.md`; I accept it, ask for changes, or revert.
- ADR review mechanics (the `okf-adr-review` skill carries the full flow): I find pending decisions with `bash scripts/okf pending`. Accepting flips the status to `accepted`, and the ADR then binds future work; rejecting reverts the work built on it, per its rollback trigger. When I tell you to accept or reject a proposed ADR, make the status edit and any reversal yourself and log the outcome in `docs/log.md` — the decision is mine, the edit can be yours.
- Reserved for me: changing `docs/GOAL.md`, superseding or contradicting an accepted ADR, and the actions the guardrails below mark as needing my go-ahead. When work can't proceed without one of these, record the blocker in `docs/log.md` and ask instead of working around it.

# Guardrails (hold in every session)

Tests and verification:

- Run the repo's test command (see Verification commands) after every change and before checking off any milestone. A milestone with failing tests is not done.
- Never delete, skip, weaken, or mark as flaky a failing test or check to get a green run. Fix the code; if the test itself is wrong, say so and get my confirmation before changing it.
- Report outcomes as they are. Failures, partial progress, and skipped verifications go in the summary and `docs/log.md`, not under the rug.

Security:

- Never write secrets — API keys, tokens, passwords, private keys, connection strings — into tracked files. Read them from the environment, and before creating an env or credentials file, confirm `.gitignore` covers it.
- Document required and optional environment variables in a committed `.env.example` holding placeholder values only; real values live in the git-ignored `.env`. The installers ignore `.env` and `.env.*` while keeping `.env.example` trackable. State in `.env.example` how the stack loads `.env` — and when nothing does, say so and show the export step, because "copy to `.env`" instructions for a stack with no loader fail silently.
- The Claude Code settings in this repo deny reading `.env` files so secrets stay out of agent context; honor the same rule here even though Codex has no mechanical enforcement — never read `.env` into context. If a task seems to require reading `.env`, stop and ask me.
- Treat changes touching auth, sessions, input parsing, file paths, network exposure, crypto, or permissions as security-sensitive: validate input at trust boundaries, use parameterized queries, grant least privilege, and run `bash scripts/okf adr-suggest`; when it flags the change, record the decision as a proposed ADR.
- New runtime dependencies are decision-shaped: the proposed ADR names the alternatives considered and the maintenance and security tradeoff.

Needs my explicit go-ahead, every time:

- Force pushes or history rewrites on shared branches; deleting or migrating stored data; deleting files beyond the task's scope.
- Publishing, deploying, releasing, or calling external services with side effects.

# Workflow for each task

1. Impact analysis: name the specs and ADRs that govern the target files.
2. Implement. Run `make test` and make it pass.
3. Knowledge alignment: run `bash scripts/okf check-stale` when available. If behavior or a contract changed, update the governing spec or ADR to match, and add a dated entry to `/docs/log.md`, newest first (ISO `YYYY-MM-DD` headings). If no doc change is warranted, add a one-line entry to `/docs/log.md` saying why. New spec or ADR files also get added to their directory's `index.md`.
4. ADR check: run `bash scripts/okf adr-suggest` for dependency, persistence, cache/queue/worker, auth/security/privacy, public API, deployment, or ownership-boundary changes. Draft an ADR only for a real decision.

# Verification commands

- Tests: `make test` (fully offline; established as the canonical command in milestone 1)
- Lint/typecheck: none beyond the `python3 -m compileall` syntax pass inside `make test`; no third-party linter per ADR-0001 (stdlib-only)
- Run locally: `make run` (scheduler plus status page); `make cycle` (one fetch/verdict/digest cycle, then exit)
- OKF stale map: `bash scripts/okf check-stale`
