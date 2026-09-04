#!/usr/bin/env python3
"""Check every `# EXPECT:` comment in fixtures/tests against what detect.py actually says.

The README used to claim the fixtures all matched. One of them had not matched since the
mock-only rule was removed, and nothing noticed, because the claim was prose rather than a
check. This is the check.
"""
import json, os, re, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "fixtures", "tests")
EXPECT = re.compile(r"#\s*EXPECT:\s*([A-Z_]+)(?:\s*/\s*([a-z-]+))?")
DEF = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)")

def expectations(path):
    pending, out = None, {}
    for line in open(path, encoding="utf-8"):
        m = EXPECT.search(line)
        if m:
            pending = (m.group(1), m.group(2) or "")
            continue
        d = DEF.match(line)
        if d and pending:
            out[d.group(1)] = pending
            pending = None
    return out

fail = 0
total = 0
for f in sorted(os.listdir(TESTS)):
    if not (f.startswith("test_") and f.endswith(".py")):
        continue
    path = os.path.join(TESTS, f)
    want = expectations(path)
    got = {r["test"]: (r["verdict"], r["reason"].split(":")[0])
           for r in json.loads(subprocess.run(
               [sys.executable, os.path.join(HERE, "detect.py"), path],
               capture_output=True, text=True, check=True).stdout)}
    for name, (v, why) in want.items():
        total += 1
        actual = got.get(name)
        if actual is None:
            print("MISSING  %s::%s" % (f, name)); fail += 1
        elif actual[0] != v or (why and actual[1] != why):
            print("MISMATCH %s::%s  expected %s/%s  got %s/%s"
                  % (f, name, v, why, actual[0], actual[1])); fail += 1

print("%d expectation(s), %d mismatch(es)" % (total, fail))
sys.exit(1 if fail else 0)
