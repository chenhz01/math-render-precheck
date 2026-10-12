# math-render-precheck

math-render-precheck is a static preflight for math in Markdown: it catches unpaired `$`/`$$`/`\(`/`\[` delimiters and common LaTeX traps (braceless `\frac`, raw `%`, `\left` without `\right`) before your renderer silently mangles them. Pure stdlib, no rendering engine, offline. Confidence: High (≥80%) for delimiter rules, per the 65-case suite.

## Problem

Math renders broken in the *worst* way: silently. One stray `$` turns the rest of a paragraph into italic soup; a raw `%` starts a LaTeX comment that eats everything after it; a braceless `\frac12` renders as an error box on some engines and as garbage on others. Reviewers catch these only after publishing, and only on the page they happened to open. There is no cheap gate between "author wrote math" and "renderer consumed math".

## How it works

1. **Segmentation** — text is split into paragraphs (blank-line separated); fenced code blocks (```/~~~) and inline code spans are stripped so `$` inside them never counts.
2. **Dollar scanner** — an escape-aware character scan classifies `$..$` (inline) and `$$..$$` (display) spans; an unclosed span at paragraph end is `unbalanced-inline` (error); an unclosed `$$` at document end is `unclosed-display` (error).
3. **Body rules** — inside every math span: `\left`≠`\right` counts → error; `\frac` not followed by `{` → error; raw `%` → warning; `\\` in inline math → warning; empty span → warning.
4. **Bracket pairing** — `\(`/`\)` and `\[/\]` counts must match within a paragraph, else `mismatched-paren` (error). Both delimiters plus `$` in one paragraph → `mixed-delimiters` warning.
5. **Exit contract** — 0 clean or warnings, 1 errors, 2 I/O failure. `--json` for CI.

## Quickstart (~2 min)

```bash
# step 1: precheck a doc (~0.1 s)
python math_render_precheck.py paper.md
# step 2: CI mode
python math_render_precheck.py paper.md --json
# step 3: stdin
cat chapter.md | python math_render_precheck.py -
# full suite (~1 s)
python self_test.py   # SUMMARY: PASS 65/65 [Measured]
```

Library use: `check_text(text)` → `{"paragraphs": int, "findings": [dict]}`.

## Why not X? (as of 2026-10-13)

**No direct equivalent found as of 2026-10-13** — no standalone stdlib-only static scanner for LaTeX delimiter pairing and render-trap detection in Markdown was located in the searched space. Nearest adjacent options:

- **KaTeX / MathJax render diagnostics** — they report errors at render time, in the browser or build step, *after* the toolchain has run; you need a JS toolchain and the error surfaces are engine-specific rather than a stable lint contract.
- **markdownlint (Node.js)** — general Markdown rules; it has no math-delimiter awareness and cannot count `\left` vs `\right` inside a span.
- **latexlint / chktex (full LaTeX toolchain)** — designed for complete `.tex` documents; overkill and heavyweight for Markdown prose that merely embeds math, and requires a TeX distribution.
- **Prettier --check** — formats code, ignores math semantics entirely.

## Performance

All numbers [Measured] on this machine (Windows, Python 3.x, single run):

| Input | Time | Command |
|---|---|---|
| 440 KB, 10,000 paragraphs (5,000 findings) | 0.134 s | see repro below |
| 65-case self-test suite | 0.178 s | `python self_test.py` |

Repro:

```bash
python -c "import time,math_render_precheck as m; t='\n\n'.join('para %d with $x+%d$ inline and $$y_%d$$ display'%(i,i,i) for i in range(5000)); t0=time.perf_counter(); r=m.check_text(t); print('%.3f s'%(time.perf_counter()-t0), len(r['findings']),'findings')"
```

## Minimal Fallback (PLAN B)

No Python: `grep -n '\$' paper.md | awk -F'$' 'NF%2==0 {print}'` flags lines with an odd dollar count; search for `\frac[^{]` with your editor to catch braceless fractions. You lose escape-awareness (`\$` false-positives), code-span protection, display/inline distinction, and the exit-code contract.

## Design Trade-offs

Priority order: **no-false-positives-in-prose > catch-real-traps > zero-dependency > syntax completeness**. The dollar scanner is deliberately escape-aware and code-span-aware even though that makes it slower than a naive `count('$')` — a linter that flags `\$5` in pricing prose gets uninstalled in a week. `unescaped-percent` and `dbl-backslash-inline` are warnings, not errors, because some renderers tolerate them; delimiter pairing is an error because no mainstream renderer tolerates it. Full LaTeX grammar parsing was explicitly rejected: the goal is a fast preflight, not a compiler.

## Limits & Second-order Effects

- No real LaTeX parsing: `\frac{a}{b}` with unbalanced inner braces is not caught; only the first-token trap is.
- `\(`/`\)` and `\[/\]` are counted per paragraph — delimiters intentionally spanning paragraphs (rare, non-standard) will false-positive.
- Multi-line display math is handled, but display math inside lists is treated as one paragraph with its indentation, which is fine for counting but not for exotic nesting.
- Second-order: authors may start writing "lint-safe" but awkward math (extra braces everywhere) to please the checker — keep the rule set minimal and let humans own style.
- Engine divergence: what renders on KaTeX may not on MathJax; this tool checks the *common* subset, not per-engine behavior.

## FAQ

**Q: Does it render or download anything?**
No. Pure static scan, fully offline.

**Q: Why is raw `%` only a warning?**
Some Markdown+MathJax setups treat `%` literally; deleting it automatically would be wrong, so we flag it for human judgment.

**Q: Can I use it on plain `.tex` files?**
Partially — paragraph rules still apply, but preamble/macro constructs will confuse the dollar scanner. It targets Markdown-embedded math.

**Q: When NOT to use this tool?**
If your pipeline already runs a full LaTeX build (chktex-covered), if your math lives in Jupyter notebooks (they execute and reveal errors), or if your docs have no math at all — then this adds noise for nothing.

**Q: Does it handle Rmarkdown or Quarto?**
It handles the math spans; chunk fences with other languages are skipped like any fenced block.

## [Core Assumptions]

1. Math in Markdown is written with `$..$`, `$$..$$`, `\(..\)`, or `\[…\]` delimiters — the four-dialect convention that dominates rendering engines.
2. Delimiter pairing is a hard, engine-independent requirement, while percent/backslash traps are engine-dependent and deserve warnings.
3. Code spans and fences must be math-free zones; any `$` inside them is literal text.
4. A fast static preflight in CI beats a slow full-render check for most documentation workflows.

Confidence: High (≥80%) for the five error rules (65-case suite); Medium (60–79%) for the claim that dollar-scan segmentation matches renderer behavior across engines — engine edge cases are documented as limits, not verified empirically. Data as of 2026-10-13.

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 105 purpose-built AI-engineering tools across neglected niches.

Related tools: [postmortem-template-lint](https://github.com/chenhz01/postmortem-template-lint) · [deprecation-timeline-audit](https://github.com/chenhz01/deprecation-timeline-audit) · [pr-size-scorer](https://github.com/chenhz01/pr-size-scorer)
