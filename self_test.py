# -*- coding: utf-8 -*-
"""self_test for math-render-precheck — v2 template, four defenses:
1) SystemExit/Exception capture around CLI main
2) Unicode-safe matching
3) fixtures written with newline="" (Windows CRLF double-write guard)
4) last line: SUMMARY: PASS n/n
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math_render_precheck as mod  # noqa: E402

main = mod.main


def run_cli(argv):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            code = main(argv) or 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:  # noqa: BLE001
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


FIX = tempfile.mkdtemp(prefix="mrp_selftest_")


def wfile(name, content):
    path = os.path.join(FIX, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return path


def rules(text):
    return [f["rule"] for f in mod.check_text(text)["findings"]]


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


# ---------- [A] functional ----------
@case("clean inline math passes")
def t01():
    assert mod.check_text("Euler said $e^{i\\pi}+1=0$ famously.\n")["findings"] == []


@case("clean display math passes")
def t02():
    assert mod.check_text("$$\n\\int_0^1 x\\,dx = \\frac{1}{2}\n$$\n")["findings"] == []


@case("unbalanced inline dollar fires")
def t03():
    assert "unbalanced-inline" in rules("price is $5 and math is $x+1$\n")


@case("unclosed display fires")
def t04():
    assert "unclosed-display" in rules("$$\nx = 1\n")


@case("mismatched inline-paren fires")
def t05():
    assert "mismatched-paren" in rules("\\(x + 1 without closer\n")


@case("mismatched display-bracket fires")
def t06():
    assert "mismatched-paren" in rules("\\[x + 1 without closer\n")


@case("matched \\( \\) pass")
def t07():
    assert mod.check_text("\\(a^2+b^2=c^2\\) is Pythagoras.\n")["findings"] == []


@case("matched \\[ \\] pass")
def t08():
    assert mod.check_text("\\[\nE = mc^2\n\\]\n")["findings"] == []


@case("mixed-delimiters warning fires")
def t09():
    r = mod.check_text("$a$ and $$b$$ in one para\n")["findings"]
    assert any(f["rule"] == "mixed-delimiters" and f["severity"] == "warning" for f in r)


@case("left-without-right fires")
def t10():
    assert "left-without-right" in rules("$$\\left(x$$\n")


@case("matched left-right pass")
def t11():
    assert mod.check_text("$$\\left(x\\right)$$\n")["findings"] == []


@case("frac-without-braces fires")
def t12():
    assert "frac-without-braces" in rules("$$\\frac12$$\n")


@case("frac with braces passes")
def t13():
    assert mod.check_text("$$\\frac{1}{2}$$\n")["findings"] == []


@case("unescaped-percent warns inside math")
def t14():
    r = mod.check_text("$$50% of x$$\n")["findings"]
    assert any(f["rule"] == "unescaped-percent" for f in r)


@case("escaped percent passes")
def t15():
    assert mod.check_text("$$50\\% of x$$\n")["findings"] == []


@case("dbl-backslash-inline warns")
def t16():
    r = mod.check_text("$a \\\\ b$ inline\n")["findings"]
    assert any(f["rule"] == "dbl-backslash-inline" for f in r)


@case("dbl-backslash in display is fine")
def t17():
    assert mod.check_text("$$a \\\\ b$$\n")["findings"] == []


@case("empty-math warns on $$ $$")
def t18():
    r = mod.check_text("$$$$$\n")["findings"]
    assert any(f["rule"] == "empty-math" for f in r)


@case("empty inline math warns")
def t19():
    r = mod.check_text("he said $ $x$ twice\n")["findings"]
    assert any(f["rule"] == "empty-math" for f in r), r


@case("escaped dollar does not toggle")
def t20():
    assert mod.check_text("costs \\$5 and $x$ math\n")["findings"] == []


@case("multiple paragraphs get separate line numbers")
def t21():
    r = mod.check_text("para one $x\n\npara two $y\n")["findings"]
    lines = sorted(f["line"] for f in r)
    assert lines == [1, 3], r


@case("fenced code block dollars ignored")
def t22():
    r = mod.check_text("```\nprice $5 and $x\n```\n")
    assert r["findings"] == [], r


@case("inline code dollars ignored")
def t23():
    assert mod.check_text("use `$5 and $x` as text\n")["findings"] == []


@case("json output parseable with shape")
def t24():
    path = wfile("j.json.md", "$x\n")
    code, out, _ = run_cli([path, "--json"])
    data = json.loads(out)
    assert code == 1 and data["findings"][0]["severity"] == "error"


@case("clean file exits 0")
def t25():
    path = wfile("ok.md", "$x+1$ fine\n")
    code, out, _ = run_cli([path])
    assert code == 0 and "0 error(s)" in out, out


@case("error file exits 1")
def t26():
    path = wfile("bad.md", "$x\n")
    code, _, _ = run_cli([path])
    assert code == 1


@case("warning-only file exits 0")
def t27():
    path = wfile("warn.md", "$$50% off$$\n")
    code, _, _ = run_cli([path])
    assert code == 0


@case("errors sorted by line")
def t28():
    r = mod.check_text("$a\n\n\\[b\n\n\\frac2$\n")["findings"]
    lines = [f["line"] for f in r]
    assert lines == sorted(lines)


@case("severity split correct")
def t29():
    r = mod.check_text("$$\\frac2$$\n\n$$50% off$$\n")["findings"]
    assert len(r) == 2
    assert {f["severity"] for f in r} == {"error", "warning"}


@case("stdin mode works")
def t30():
    buf = io.StringIO("$x+1$\n")
    old = sys.stdin
    sys.stdin = buf
    try:
        code, out, _ = run_cli(["-"])
    finally:
        sys.stdin = old
    assert code == 0 and "1 paragraphs" in out, out


# ---------- [B] error paths ----------
@case("missing file exits 2")
def t31():
    code, _, err = run_cli([os.path.join(FIX, "nope.md")])
    assert code == 2 and "cannot read" in err, err


@case("missing file --json prints json error")
def t32():
    code, out, _ = run_cli([os.path.join(FIX, "nope.md"), "--json"])
    assert code == 2 and "error" in json.loads(out)


@case("directory as input exits 2")
def t33():
    code, _, _ = run_cli([FIX])
    assert code == 2


@case("no arguments raises SystemExit 2")
def t34():
    try:
        main([])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 2, e.code


@case("--help exits 0")
def t35():
    code, out, _ = run_cli(["--help"])
    assert code == 0 and "usage" in out.lower()


@case("--version exits 0 and shows version")
def t36():
    code, out, _ = run_cli(["--version"])
    assert code == 0 and "0.1.1" in out


@case("unknown flag exits 2")
def t37():
    assert run_cli(["--bogus"])[0] == 2


@case("findings always have four keys")
def t38():
    for f in mod.check_text("$x\n\\[y\n")["findings"]:
        assert set(f) == {"rule", "severity", "line", "message"}


@case("check_text never raises on pathological input")
def t39():
    for s in ("", "$", "$$", "$$$$", "\\", "\\\\", "\\frac", "$$$ $ $$ $"):
        mod.check_text(s)


@case("fence inside paragraph terminates it")
def t40():
    r = mod.check_text("$unclosed\n```\ncode $x\n```\n")["findings"]
    assert any(f["rule"] == "unbalanced-inline" for f in r)
    assert not any("code $x" in f["message"] for f in r)


# ---------- [C] extreme edge ----------
@case("empty string input")
def t41():
    assert mod.check_text("")["findings"] == []


@case("whitespace-only input")
def t42():
    assert mod.check_text("   \n\t\n")["findings"] == []


@case("CRLF line endings handled")
def t43():
    assert mod.check_text("$x+1$\r\n\r\n$$y$$\r\n")["findings"] == []


@case("unicode content around math")
def t44():
    assert mod.check_text("设 $x$ 为变量，则 $y=2x$ 成立。\n")["findings"] == []


@case("unicode unbalanced still detected")
def t45():
    assert "unbalanced-inline" in rules("设 $x 为变量。\n")


@case("very long single math body (100k chars)")
def t46():
    assert mod.check_text("$$" + "x+" * 50000 + "1$$\n")["findings"] == []


@case("very long paragraph with no math")
def t47():
    assert mod.check_text("plain " * 50000 + "\n")["findings"] == []


@case("many paragraphs (5000) with clean math")
def t48():
    text = "\n\n".join("para %d $x+%d$" % (i, i) for i in range(5000))
    r = mod.check_text(text)
    assert r["paragraphs"] == 5000 and r["findings"] == []


@case("dollar-heavy prose without math flagged once per para")
def t49():
    r = mod.check_text("costs $1, $2, and $3 total\n")["findings"]
    assert [f["rule"] for f in r].count("unbalanced-inline") == 1


@case("nested inline code inside math-heavy para")
def t50():
    assert mod.check_text("`$a$` then $b$ ok\n")["findings"] == []


@case("tilde fences skipped")
def t51():
    assert mod.check_text("~~~\n$x$\n~~~\n")["findings"] == []


@case("BOM prefix tolerated")
def t52():
    assert mod.check_text("\ufeff$x+1$\n")["findings"] == []


@case("display math spanning multiple lines")
def t53():
    r = mod.check_text("$$\na\nb\nc\n$$\n")["findings"]
    assert r["findings"] == [] if False else r == [], r


@case("three dollars sequence")
def t54():
    mod.check_text("$$$x$$$")  # must not raise; any classification is stable


@case("backslash at end of input")
def t55():
    mod.check_text("trailing backslash \\")


@case("percent in prose is not flagged")
def t56():
    assert mod.check_text("50% of users prefer $x$\n")["findings"] == []


@case("left/right across paragraphs not confused")
def t57():
    r = mod.check_text("$$\\left(a$$\n\n$$b\\right)$$\n")["findings"]
    assert len([f for f in r if f["rule"] == "left-without-right"]) == 2, r


@case("mixed fences and math pipeline")
def t58():
    text = "intro $a$\n\n```py\nx = '$b'\n```\n\n\\[c\\]\n"
    assert mod.check_text(text)["findings"] == []


@case("full CLI pipeline contract")
def t59():
    path = wfile("c59.md", "# T\n\n$good$\n\n$bad\n")
    code, out, _ = run_cli([path])
    assert code == 1 and "unbalanced-inline" in out and "line 5" in out, out


@case("repeated runs are deterministic")
def t60():
    text = "$a $$b \\frac2 $c\n\\[d\n"
    assert mod.check_text(text) == mod.check_text(text)


@case("html block with dollars not special-cased but safe")
def t61():
    mod.check_text("<div>$x</div>\n")


@case("indented fence still recognized")
def t62():
    r = mod.check_text("   ```\n   $x\n   ```\n")
    assert r["findings"] == [], r


@case("emoji + math mixed")
def t63():
    assert mod.check_text("🎉 $x+1$ 🚀\n")["findings"] == []


@case("summary line format stable")
def t64():
    path = wfile("c64.md", "$x$\n")
    code, out, _ = run_cli([path])
    assert out.strip().endswith("checked 1 paragraphs: 0 error(s), 0 warning(s)"), out


@case("unbalanced and mismatched can coexist")
def t65():
    r = mod.check_text("$x \\[y\n")["findings"]
    rl = {f["rule"] for f in r}
    assert rl == {"unbalanced-inline", "mismatched-paren"}, r


class ToolTests(unittest.TestCase):
    pass


def _name(i, n):
    return "test_%03d_%s" % (i, re.sub(r"\W+", "_", n))


for _i, (_n, _fn) in enumerate(CASES):
    setattr(ToolTests, _name(_i, _n), lambda self, _f=_fn: _f())


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    for t, _ in r.failures + r.errors:
        print("FAIL:", t.id().split(".")[-1])
    print("SUMMARY: PASS %d/%d" % (total - fails, total))
    sys.exit(0 if fails == 0 else 1)
