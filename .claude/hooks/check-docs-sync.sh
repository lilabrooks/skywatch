#!/usr/bin/env bash
# Destination in your repo: .claude/hooks/check-docs-sync.sh
# No chmod needed: settings.json invokes this via `bash`.
#
# Stop hook: when Claude Code tries to finish a turn, this first checks whether
# implementation files changed without anything under docs/ being touched. If
# scripts/okf is installed, it then checks whether the touched source areas have
# matching mapped docs or a log.md rationale. No infinite loop.

ROOT="${CLAUDE_PROJECT_DIR:-.}"

changed=$( { git -C "$ROOT" diff --name-only HEAD; git -C "$ROOT" ls-files --others --exclude-standard; } 2>/dev/null | sort -u )

code_changed=$(printf '%s\n' "$changed" \
  | grep -vE '^(docs/|\.claude/|CLAUDE\.md|CLAUDE\.local\.md|README\.md|CHANGELOG\.md|LICENSE|\.gitignore|\.editorconfig|scripts/okf)' \
  | grep -v '^$' \
  | head -n 1)
docs_changed=$(printf '%s\n' "$changed" | grep -E '^docs/' | head -n 1)

if [ -n "$code_changed" ] && [ -z "$docs_changed" ]; then
  cat <<'EOF'
{"decision": "block", "reason": "Code changed this session but nothing under /docs was updated. Per the CLAUDE.md workflow: if behavior or a contract changed, update the governing file in /docs/specs or /docs/adr and add a dated entry to /docs/log.md. If no doc change is warranted, add a one-line entry to /docs/log.md saying why."}
EOF
  exit 0
fi

if [ -n "$code_changed" ] && [ -f "$ROOT/scripts/okf" ]; then
  stale_result=$(OKF_HOOK=1 OKF_ROOT="$ROOT" bash "$ROOT/scripts/okf" check-stale 2>/dev/null)
  if [ -n "$stale_result" ]; then
    printf '%s\n' "$stale_result"
    exit 0
  fi
fi

exit 0
