#!/usr/bin/env bash
# Destination in your repo: .claude/hooks/check-okf-version.sh
# No chmod needed: settings.json invokes this via `bash`.
#
# SessionStart hook: compares the OKF version this repo declares in docs/index.md
# against the latest spec version published on the OKF main branch, and the
# kit_version this repo declares against the kit's published VERSION file. When
# either differs, it injects a note into Claude's context; the "OKF version
# policy" and "Kit version policy" sections in CLAUDE.md tell Claude what to do.
# Fails silent (exit 0, no output) when offline, when docs/index.md carries no
# kit_version stamp, or if the upstream layouts change.

SPEC_URL="https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md"
KIT_VERSION_URL="https://raw.githubusercontent.com/lilabrooks/claude-okf-repo-kit/main/VERSION"
ROOT="${CLAUDE_PROJECT_DIR:-.}"

notes=""

latest=$(curl -fsSL --max-time 5 "$SPEC_URL" 2>/dev/null \
  | grep -m1 -oE 'Version [0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+')
declared=$(grep -m1 -oE 'okf_version:[[:space:]]*"?[0-9]+\.[0-9]+"?' "$ROOT/docs/index.md" 2>/dev/null \
  | grep -oE '[0-9]+\.[0-9]+')

if [ -n "$latest" ] && [ "$latest" != "$declared" ]; then
  notes="OKF version check: the latest OKF spec version on the official main branch is $latest. This repo's docs/index.md declares okf_version ${declared:-(none)}. The OKF version policy in CLAUDE.md applies."
fi

kit_declared=$(grep -m1 -oE 'kit_version:[[:space:]]*"?[0-9]+\.[0-9]+\.[0-9]+"?' "$ROOT/docs/index.md" 2>/dev/null \
  | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

if [ -n "$kit_declared" ]; then
  kit_latest=$(curl -fsSL --max-time 5 "$KIT_VERSION_URL" 2>/dev/null \
    | grep -m1 -oE '[0-9]+\.[0-9]+\.[0-9]+')
  if [ -n "$kit_latest" ] && [ "$kit_latest" != "$kit_declared" ]; then
    kit_note="Kit version check: this repo was installed from claude-okf-repo-kit $kit_declared and the published kit version is $kit_latest. The Kit version policy in CLAUDE.md applies."
    if [ -n "$notes" ]; then
      notes="$notes $kit_note"
    else
      notes="$kit_note"
    fi
  fi
fi

if [ -n "$notes" ]; then
  cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "$notes"}}
EOF
fi

exit 0
