#!/usr/bin/env python3
"""Run the real analyzer against bundled cases before it is trusted with your code.

The assertions that prove this analyzer works live on the author's laptop, where nobody
running the play can see them. This feeds the shipped detect.py and audit_dir.py their
own bundled cases at run time, and the presentation withholds its verdict if any fail.

Two things this covers that a naive self-check does not, both because a green check above
a broken analyzer is worse than no check at all:

  every verdict has a POSITIVE case. A rule with only negative cases can be deleted and
  the self-check still passes. Swapping NOT_ANALYZED for EXAMINED in the real analyzer
  was proved to keep a 16/16 green while blind spots silently became clean results.

  DISCOVERY is checked, not only analysis. A scan whose filename filter is broken finds
  nothing and reports a clean tree. The discovery case writes one file into a scratch
  directory at run time and asserts it comes back, so nothing test-shaped needs to ship
  outside the demo corpus.

    selfcheck.py            -> JSON {passed, total, failures}
"""
import json
import os
import os, os, re, subprocess, sys, tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "demo", "tests")
EXPECT = re.compile(r"#\s*EXPECT:\s*([A-Z_]+)(?:\s*/\s*([a-z-]+))?")
DEF = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)")

# Every verdict the analyzer can emit needs a positive case here, or deleting the rule
# that produces it would not be noticed.
MUST_COVER = {"CANNOT_FAIL", "NO_VALUE_CHECK", "WEAK", "EXAMINED", "NOT_ANALYZED"}


def run_json(args):
    # spawned as a literal so the command can be checked against deps.toml
    p = subprocess.run(["python3"] + args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "").strip()[:200] or "exit %d" % p.returncode)
    return json.loads(p.stdout)


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


def main():
    failures, total = [], 0
    seen = set()

    # ---- analysis cases: the real detect.py against the bundled corpus
    if not os.path.isdir(CASES):
        failures.append({"case": "cases-present",
                         "detail": "bundled case directory is missing"})
    else:
        for fn in sorted(os.listdir(CASES)):
            if not (fn.startswith("test_") and fn.endswith(".py")):
                continue
            path = os.path.join(CASES, fn)
            want = expectations(path)
            if not want:
                continue
            try:
                rows = run_json([os.path.join(HERE, "detect.py"), path])
            except Exception as e:
                failures.append({"case": fn, "detail": "analyzer failed: %s" % e})
                total += len(want)
                continue
            got = {r["test"]: (r["verdict"], r["reason"].split(":")[0]) for r in rows}
            for name, (verdict, reason) in want.items():
                total += 1
                seen.add(verdict)
                actual = got.get(name)
                if actual is None:
                    failures.append({"case": "%s::%s" % (fn, name),
                                     "detail": "analyzer returned no verdict"})
                elif actual[0] != verdict or (reason and actual[1] != reason):
                    failures.append({
                        "case": "%s::%s" % (fn, name),
                        "detail": "expected %s/%s, produced %s/%s"
                                  % (verdict, reason, actual[0], actual[1])})

    # ---- coverage: a rule with no positive case is a rule nothing can protect
    for verdict in sorted(MUST_COVER - seen):
        total += 1
        failures.append({"case": "coverage:%s" % verdict,
                         "detail": "no bundled case asserts this verdict, so removing "
                                   "the rule that produces it would not be noticed"})

    # ---- discovery case: a broken filename filter finds nothing and reads as clean
    total += 1
    try:
        with tempfile.TemporaryDirectory() as scratch:
            sub = os.path.join(scratch, "pkg")
            os.makedirs(sub)
            with open(os.path.join(sub, "test_discovery_probe.py"), "w") as fh:
                fh.write("def test_probe():\n    pass\n")
            with open(os.path.join(sub, "helper.py"), "w") as fh:
                fh.write("def not_a_test():\n    pass\n")
            found = run_json([os.path.join(HERE, "audit_dir.py"), scratch])
            if found.get("files_scanned") != 1 or found.get("total_tests") != 1:
                failures.append({
                    "case": "discovery:finds-a-test-file",
                    "detail": "expected 1 file and 1 test in a scratch tree, got %s file(s) "
                              "and %s test(s)" % (found.get("files_scanned"),
                                                  found.get("total_tests"))})
    except Exception as e:
        failures.append({"case": "discovery:finds-a-test-file",
                         "detail": "discovery failed: %s" % e})


    # ---- git escapes non-ASCII paths before printing them, so a wrapper without
    # core.quotePath=false reads back a filename that does not exist. On a repository
    # with an accented filename this made blast-radius report no changes at all.
    total += 1
    try:
        _src = open(os.path.join(HERE, "git_dates.py"), encoding="utf-8").read()
        if "core.quotePath=false" not in _src:
            failures.append({
                "case": "paths:non-ascii-are-not-escaped",
                "detail": "the git wrapper does not pass core.quotePath=false, so a path "
                          "with a non-ASCII character comes back as an escaped string "
                          "and every file named that way is silently missed"})
    except OSError as _e:
        failures.append({"case": "paths:non-ascii-are-not-escaped",
                         "detail": "could not read the analyzer: %s" % _e})


    # ---- the play must run with no arguments at all
    #
    # A reviewer pulled all nine and found three that did not: two declared required
    # parameters and refused, and one defaulted to the reader's real history instead of
    # the bundled example. No self-check looked at the frontmatter, so nothing caught it.
    total += 1
    try:
        _mt = open(os.path.join(HERE, "..", "main.ts"), encoding="utf-8").read()
        _params = _mt.split("* parameters:")[1].split("* metadata:")[0] if "* parameters:" in _mt else ""
        _required = [ln for ln in _params.split(chr(10)) if "required: true" in ln]
        if _required:
            failures.append({
                "case": "runs-bare:no-required-parameters",
                "detail": "%d parameter(s) are declared required, so `rote play run "
                          "<this>` refuses instead of showing the bundled example"
                          % len(_required)})
    except Exception as _e:
        failures.append({"case": "runs-bare:no-required-parameters",
                         "detail": "could not read the frontmatter: %s" % _e})

    print(json.dumps({
        "passed": total - len(failures),
        "total": total,
        "failures": failures[:10],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
