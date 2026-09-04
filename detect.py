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

    # Assertions are often delegated to a same-file helper (flask's common_object_test).
    # Resolve those transitively, or every caller looks assertion-free.
    ALLFN = (ast.FunctionDef, ast.AsyncFunctionDef)

    def _asserts_directly(node):
        for n in ast.walk(node):
            if isinstance(n, ast.Assert):
                return True
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                a = n.func.attr
                if a.startswith("assert") or a in ("fail", "raises"):
                    return True
        return False

    helpers = {n.name: n for n in ast.walk(tree) if isinstance(n, ALLFN)}
    asserting = {k for k, v in helpers.items() if _asserts_directly(v)}
    changed = True
    while changed:                     # a helper calling an asserting helper also asserts
        changed = False
        for name, node in helpers.items():
            if name in asserting:
                continue
            callees = {c.func.id for c in ast.walk(node)
                       if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            if callees & asserting:
                asserting.add(name)
                changed = True

    out, bodies = [], {}
    TESTFN = (ast.FunctionDef, ast.AsyncFunctionDef)

    def collect(body):
        found = []
        for n in body:
            if isinstance(n, TESTFN) and n.name.startswith("test"):
                found.append(n)
            elif isinstance(n, ast.ClassDef):
                found.extend(m for m in n.body
                             if isinstance(m, TESTFN) and m.name.startswith("test"))
        return found

    for fn in collect(tree.body):
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
        swallowed_tries = [
            n for n in ast.walk(fn) if isinstance(n, ast.Try)
            and any(h.body and isinstance(h.body[0], ast.Pass)
                    and (h.type is None or (isinstance(h.type, ast.Name)
                                            and h.type.id in ("Exception", "BaseException")))
                    for h in n.handlers)]
        inside = set()
        for t in swallowed_tries:
            for stmt in t.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Assert):
                        inside.add(id(sub))
        all_checks = [a for a in asserts]
        swallow = bool(all_checks) and all(id(a) in inside for a in all_checks) and not unit_as
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

        # does this test delegate its assertions to a helper defined in this file?
        helper_assert = bool((called & asserting) - {fn.name})

        # EXAMINED is the fall-through: the test was read and no theatre pattern matched.
        # NOT_ANALYZED is reserved for a real blind spot, where the assertions live in a
        # helper this reader did not follow. Collapsing the two made a clean suite and an
        # unread one look identical, which is the failure this play exists to catch.
        v, why = "EXAMINED", ""
        if helper_assert and not asserts and not unit_as:
            v, why = "NOT_ANALYZED", "assertions-delegated-to-helper"
        elif asserts and not unit_as and all(const_only(a.test) for a in asserts):
            v, why = "CANNOT_FAIL", "asserts-literal"
        elif unit_literal and not asserts:
            v, why = "CANNOT_FAIL", "asserts-literal"
        elif swallow:
            v, why = "CANNOT_FAIL", "swallowed-exception"
        elif not asserts and not mock_as and not raises and not unit_as and not helper_assert:
            v, why = "NO_VALUE_CHECK", "no-assertion"
        elif skipped:
            v, why = "WEAK", "permanently-skipped"

        h = norm(ast.Module(body=fn.body, type_ignores=[]))
        if v in ("EXAMINED", "NOT_ANALYZED") and h in bodies:
            v, why = "WEAK", "duplicate-body:" + bodies[h]
        bodies.setdefault(h, fn.name)
        out.append({"test": fn.name, "verdict": v, "reason": why, "line": fn.lineno})
    return out

if __name__ == "__main__":
    print(json.dumps(analyze(sys.argv[1]), indent=1))
