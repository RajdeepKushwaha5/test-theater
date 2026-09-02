#!/usr/bin/env python3
"""test-theater prototype: find tests that cannot fail. Pure ast, never executes."""
import ast, hashlib, json, re, sys

STDLIB_ISH = {"pytest", "unittest", "mock", "os", "sys", "json", "re", "typing", "pathlib"}

def norm(node):
    """Normalized body text for duplicate detection."""
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()[:12]

def const_only(node):
    """True if expression is built purely from literals."""
    for n in ast.walk(node):
        if isinstance(n, (ast.Name, ast.Call, ast.Attribute, ast.Subscript)):
            return False
    return True

def analyze(path):
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [{"test": None, "verdict": "UNPARSEABLE", "reason": str(e), "line": 0}]

    subject, subject_mods = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            root = n.module.split(".")[0]
            if root not in STDLIB_ISH:
                subject.update(a.asname or a.name for a in n.names)
        elif isinstance(n, ast.Import):
            for a in n.names:
                root = (a.asname or a.name).split(".")[0]
                if root not in STDLIB_ISH:
                    subject_mods.add(root)

    out, bodies = [], {}
    TESTFN = (ast.FunctionDef, ast.AsyncFunctionDef)
    for fn in [n for n in ast.walk(tree) if isinstance(n, TESTFN) and n.name.startswith("test")]:
        asserts   = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        calls     = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
        mock_as   = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr.startswith("assert_")]
        unit_as   = [c for c in calls if isinstance(c.func, ast.Attribute)
                     and (re.match(r"assert[A-Z]", c.func.attr) or c.func.attr in ("fail", "assertRaises"))]
        raises    = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "raises"]
        def _dotted(d):
            d = d.func if isinstance(d, ast.Call) else d
            parts = []
            while isinstance(d, ast.Attribute):
                parts.append(d.attr); d = d.value
            if isinstance(d, ast.Name):
                parts.append(d.id)
            return ".".join(reversed(parts))
        skipped   = any(_dotted(d).split(".")[-1] == "skip" for d in fn.decorator_list)
        swallow   = any(
            h.body and isinstance(h.body[0], ast.Pass)
            and (h.type is None or (isinstance(h.type, ast.Name)
                                    and h.type.id in ("Exception", "BaseException")))
            for n in ast.walk(fn) if isinstance(n, ast.Try) for h in n.handlers)
        called    = {c.func.id for c in calls if isinstance(c.func, ast.Name)}
        called   |= {c.func.attr for c in calls if isinstance(c.func, ast.Attribute)}
        bases     = {c.func.value.id for c in calls
                     if isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name)}
        touches   = bool((subject & called) or (subject_mods & bases))

        # pytest.fail()/self.fail() is a failure TRIGGER, not a tautological assertion:
        # a test containing one can fail by construction, so it is never literal-only.
        has_fail = any(isinstance(c.func, ast.Attribute) and c.func.attr == "fail"
                       for c in unit_as)
        unit_literal = bool(unit_as) and not has_fail and all(
            all(const_only(a) for a in c.args) for c in unit_as)

        v, why = "NOT_ANALYZED", ""
        if asserts and not unit_as and all(const_only(a.test) for a in asserts):
            v, why = "CANNOT_FAIL", "asserts-literal"
        elif unit_literal and not asserts:
            v, why = "CANNOT_FAIL", "asserts-literal"
        elif swallow:
            v, why = "CANNOT_FAIL", "swallowed-exception"
        elif not asserts and not mock_as and not raises and not unit_as:
            v, why = "NO_VALUE_CHECK", "no-assertion"
        elif not asserts and not unit_as and mock_as:
            v, why = "NO_VALUE_CHECK", "mock-only"
        elif skipped:
            v, why = "WEAK", "permanently-skipped"

        h = norm(ast.Module(body=fn.body, type_ignores=[]))
        if v == "NOT_ANALYZED" and h in bodies:
            v, why = "WEAK", "duplicate-body:" + bodies[h]
        bodies.setdefault(h, fn.name)
        out.append({"test": fn.name, "verdict": v, "reason": why, "line": fn.lineno})
    return out

if __name__ == "__main__":
    print(json.dumps(analyze(sys.argv[1]), indent=1))
