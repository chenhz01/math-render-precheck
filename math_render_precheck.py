#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""math-render-precheck — static preflight for math rendering in Markdown.

Catches delimiter-pairing and common LaTeX trap defects BEFORE the renderer
silently mangles them. Pure text scan: no network, no rendering engine.

Rules:
  unbalanced-inline   (error)   odd number of unescaped $ in a paragraph
  unclosed-display    (error)   $$ opened but never closed in the document
  mismatched-paren    (error)   \\( without \\) or \\[ without \\] in a paragraph
  mixed-delimiters    (warning) $..$ and $$..$$ both used in one paragraph
  left-without-right  (error)   \\left count != \\right count inside one math span
  frac-without-braces (error)   \\frac not immediately followed by {
  unescaped-percent   (warning) raw % inside math (starts a LaTeX comment)
  dbl-backslash-inline(warning) \\\\ inside inline $..$ (only valid in display)
  empty-math          (warning) empty $$$$ / $$ / $ span

Exit codes: 0 clean-or-warnings, 1 errors, 2 I/O failure.
Pure stdlib. Python 3.8+.
"""
import argparse
import json
import re
import sys

__version__ = "0.1.1"

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")


def _scan_dollars(segment):
    """Scan one paragraph segment for $ / $$ regions (escape-aware).

    Returns (inline_bodies, display_bodies, defects) where defects is a list
    of (rule, message) local to the segment.
    """
    inline, display = [], []
    defects = []
    mode = None  # None | 'inline' | 'display'
    buf = []
    i, n = 0, len(segment)
    while i < n:
        ch = segment[i]
        if ch == "\\" and i + 1 < n:
            if mode is not None:
                buf.append(segment[i:i + 2])
            i += 2
            continue
        if segment[i:i + 2] == "$$":
            if mode == "display":
                display.append("".join(buf))
                buf, mode = [], None
            elif mode == "inline":
                # $$ closing an inline span: renderer ambiguity, treat as close
                inline.append("".join(buf))
                buf, mode = [], None
            else:
                mode, buf = "display", []
            i += 2
            continue
        if ch == "$":
            if mode == "inline":
                inline.append("".join(buf))
                buf, mode = [], []
                mode = None
            elif mode is None:
                mode, buf = "inline", []
            else:  # single $ inside display: literal, keep
                buf.append(ch)
            i += 1
            continue
        if mode is not None:
            buf.append(ch)
        i += 1
    if mode == "inline":
        defects.append(("unbalanced-inline", "odd number of unescaped '$'"))
    elif mode == "display":
        defects.append(("unclosed-display", "'$$' opened but never closed"))
    return inline, display, defects


def _body_defects(body, where):
    """Rule checks applied to one math body."""
    out = []
    if body.strip() == "":
        out.append(("empty-math", "empty math span (%s)" % where))
    if body.count("\\left") != body.count("\\right"):
        out.append(("left-without-right",
                    "\\left x%d vs \\right x%d (%s)"
                    % (body.count("\\left"), body.count("\\right"), where)))
    for m in re.finditer(r"\\frac(?![a-zA-Z])", body):
        nxt = body[m.end():m.end() + 1]
        if nxt != "{":
            out.append(("frac-without-braces",
                        "\\frac not followed by '{' (%s)" % where))
            break
    if re.search(r"(?<!\\)%", body):
        out.append(("unescaped-percent",
                    "raw '%%' starts a LaTeX comment (%s)" % where))
    if where == "inline" and "\\\\" in body:
        out.append(("dbl-backslash-inline",
                    "'\\\\' line break inside inline math (%s)" % where))
    return out


def check_text(text):
    """Check Markdown text; return {"paragraphs": int, "findings": [dict]}."""
    findings = []

    def add(rule, severity, line, msg):
        findings.append({"rule": rule, "severity": severity,
                         "line": line, "message": msg})

    lines = text.splitlines()
    in_fence = False
    fence_char = None
    para_start = None
    para_buf = []

    def flush(end_line):
        if not para_buf:
            return
        segment = "\n".join(para_buf)
        # strip inline code spans so `$` in backticks never counts
        segment = INLINE_CODE_RE.sub(" ", segment)
        inline, display, defects = _scan_dollars(segment)
        for rule, msg in defects:
            add(rule, "error", para_start, msg)
        if inline and display:
            add("mixed-delimiters", "warning", para_start,
                "both $..$ and $$..$$ used in one paragraph")
        for b in inline:
            for rule, msg in _body_defects(b, "inline"):
                add(rule, "error" if rule in ("left-without-right",
                                              "frac-without-braces") else "warning",
                    para_start, msg)
        for b in display:
            for rule, msg in _body_defects(b, "display"):
                add(rule, "error" if rule in ("left-without-right",
                                              "frac-without-braces") else "warning",
                    para_start, msg)
        # \( \) and \[ \] pairing on the code-stripped segment
        for op, cl, name in (("\\(", "\\)", "inline-paren"),
                             ("\\[", "\\]", "display-bracket")):
            no, nc = segment.count(op), segment.count(cl)
            if no != nc:
                add("mismatched-paren", "error", para_start,
                    "%s: %d opener(s) vs %d closer(s)" % (name, no, nc))
        del para_buf[:]

    for idx, raw in enumerate(lines, 1):
        fm = FENCE_RE.match(raw)
        if fm:
            ch = fm.group(1)[0]
            if not in_fence:
                flush(idx)
                para_start = None
                in_fence, fence_char = True, ch
            elif ch == fence_char:
                in_fence, fence_char = False, None
            continue
        if in_fence:
            continue
        if raw.strip() == "":
            flush(idx)
            para_start = None
            continue
        if para_start is None:
            para_start = idx
        para_buf.append(raw)
    flush(len(lines))
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return {"paragraphs": len([1 for l in lines if l.strip()]), "findings": findings}


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="math-render-precheck",
        description="Static preflight for LaTeX delimiter pairing and common "
                    "math-rendering traps in Markdown.")
    p.add_argument("file", help="Markdown file ('-' for stdin)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--version", action="version",
                   version="%(prog)s " + __version__)
    args = p.parse_args(argv)
    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, "r", encoding="utf-8-sig") as f:
                text = f.read()
    except OSError as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print("error: cannot read %s: %s" % (args.file, e), file=sys.stderr)
        return 2
    result = check_text(text)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for f in result["findings"]:
            print("%-20s %-7s line %s: %s"
                  % (f["rule"], f["severity"], f["line"], f["message"]))
        print("checked %d paragraphs: %d error(s), %d warning(s)"
              % (result["paragraphs"], len(errors),
                 len(result["findings"]) - len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
