"""Second-agent config parity (kit ADR 0021 belt-and-suspenders).

The Codex hook mirrors under .codex/hooks/ must stay byte-identical to the
.claude/hooks/ originals. The safe kit updater syncs the declared mirrors on
upgrades; this guard catches hand edits and anything undeclared. Skipped
entirely when the Codex stack is absent, since it is optional.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEX_HOOKS = REPO_ROOT / ".codex" / "hooks"
CLAUDE_HOOKS = REPO_ROOT / ".claude" / "hooks"
HOOK_NAMES = ("check-docs-sync.sh", "check-okf-version.sh")


@unittest.skipUnless(CODEX_HOOKS.is_dir(), "no Codex hook mirror in this repo")
class AgentParityTest(unittest.TestCase):
    def test_codex_hook_mirrors_are_byte_identical(self):
        for name in HOOK_NAMES:
            with self.subTest(hook=name):
                mirror = CODEX_HOOKS / name
                self.assertTrue(mirror.is_file(), f"declared mirror is missing {name}")
                self.assertEqual(
                    mirror.read_bytes(),
                    (CLAUDE_HOOKS / name).read_bytes(),
                    f".codex/hooks/{name} differs from .claude/hooks/{name}; "
                    "mirrors are meant to stay byte-identical (run the kit updater)",
                )

    def test_codex_hooks_json_wires_both_hooks(self):
        hooks_json = (REPO_ROOT / ".codex" / "hooks.json").read_text()
        for name in HOOK_NAMES:
            with self.subTest(hook=name):
                self.assertIn(name, hooks_json, f".codex/hooks.json does not wire {name}")


if __name__ == "__main__":
    unittest.main()
