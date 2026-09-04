#!/usr/bin/env python3
"""Check that the Python side still emits every field the presentation reads.

The presentation is TypeScript and the producers are Python, so nothing type-checks
across that seam. When `examined_count` was added, the consumer needed a fallback for
observations that predate it, and that fallback had no coverage. The real risk was never
the fallback: it was the seam. A field renamed on the Python side fails silently in
TypeScript, as `undefined`.

This runs the producers on the bundled demo and asserts every `parsed.<field>` the
presentation reads is actually present.

    python3 verify-contract.py
"""
import json, os, re, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.ts")
DEMO = os.path.join(HERE, "demo", "tests")

if not os.path.exists(MAIN):
    print("main.ts not found next to this script; nothing to check")
    sys.exit(0)

consumed = sorted(set(re.findall(r"parsed" + re.escape(".") + r"([a-z_]+)", open(MAIN).read())))
if not consumed:
    print("no parsed.<field> reads found in main.ts")
    sys.exit(1)


def run(args):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    if p.returncode != 0:
        print("producer failed:", " ".join(args))
        print(p.stderr.strip()[:500])
        sys.exit(1)
    return json.loads(p.stdout)


audit = run([os.path.join(HERE, "audit_dir.py"), DEMO])
dates = run([os.path.join(HERE, "git_dates.py"), DEMO, json.dumps(audit)])

# git_dates is the step the presentation actually parses
missing = [f for f in consumed if f not in dates]
for f in consumed:
    print("  %-22s %s" % (f, "present" if f in dates else "MISSING"))
print()
if missing:
    print("%d field(s) the presentation reads are not emitted: %s"
          % (len(missing), ", ".join(missing)))
    sys.exit(1)
print("%d field(s) checked, all emitted" % len(consumed))
