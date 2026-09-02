#!/usr/bin/env python3
"""Audit a Python test suite for tests that structurally cannot fail. Pure ast, never
executes the suite under audit. Accepts a single test file or a directory (recursively
collects test_*.py). Reuses detect.py's analyze() unmodified, tags every finding with its
source file, and exits nonzero if the target path does not exist."""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect

root = sys.argv[1]
if not os.path.exists(root):
    print(f"error: no such file or directory: {root}", file=sys.stderr)
    sys.exit(1)

results = []
if os.path.isfile(root):
    for finding in detect.analyze(root):
        finding["file"] = os.path.basename(root)
        results.append(finding)
else:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".pytest_cache")]
        for fn in sorted(filenames):
            if fn.startswith("test_") and fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                for finding in detect.analyze(full):
                    finding["file"] = rel
                    results.append(finding)

print(json.dumps(results, separators=(",", ":")))
