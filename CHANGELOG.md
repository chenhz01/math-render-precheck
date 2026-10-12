# Changelog

## v0.1.1 — 2026-10-13
- Round-2 self-audit: two test cases used inputs that produced different rules than intended (empty-math probe hit unclosed-display; warning-only exit probe accidentally tripped unbalanced-inline). Tests rewritten to target the intended rules; tool code unchanged and already correct.
- Self-test re-run: `python self_test.py` → `SUMMARY: PASS 65/65` (was 63/65 at first draft).

## v0.1.0 — 2026-10-13
- Initial implementation: escape-aware dollar scanner (inline/display), paragraph segmentation with fence and code-span stripping, nine rules (unbalanced-inline / unclosed-display / mismatched-paren / mixed-delimiters / left-without-right / frac-without-braces / unescaped-percent / dbl-backslash-inline / empty-math), CLI (file/stdin, `--json`, exit 0/1/2 contract).
- Self-test suite (functional / error / extreme-edge tiers), 65 cases at first draft.
