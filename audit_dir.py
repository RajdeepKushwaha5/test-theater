#!/usr/bin/env python3
"""Audit a Python test suite for tests that structurally cannot fail. Pure ast, never
executes the suite under audit. Accepts a single test file or a directory (recursively
collects test_*.py).

A traversal that can partially fail must say so. os.walk skips unreadable directories
in silence by default, which turns a permissions problem into a shorter, cleaner-looking
report. Every path this cannot read is recorded and reported alongside the findings, so
a short answer is never mistaken for a clean one.
"""
import sys, os, json

sys.dont_write_bytecode = True  # never ship a __pycache__ into the play package

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect

root = sys.argv[1]
if not os.path.exists(root):
    print("error: no such file or directory: %s" % root, file=sys.stderr)
    sys.exit(1)

unreadable = []
results = []
files_scanned = 0


def note_unreadable(path, reason):
    unreadable.append({"path": path, "reason": reason})


def scan(full, rel):
    """Read one file. A file we cannot open or decode is named, never skipped quietly."""
    global files_scanned
    try:
        findings = detect.analyze(full)
    except (OSError, PermissionError) as e:
        note_unreadable(rel, type(e).__name__)
        return
    except UnicodeDecodeError:
        note_unreadable(rel, "UnicodeDecodeError")
        return
    files_scanned += 1
    for finding in findings:
        finding["file"] = rel
        results.append(finding)


if os.path.isfile(root):
    scan(root, os.path.basename(root))
else:
    # onerror fires for a directory os.walk cannot list; without it the subtree
    # disappears from the report with nothing said.
    for dirpath, dirnames, filenames in os.walk(
        root, onerror=lambda e: note_unreadable(
            os.path.relpath(getattr(e, "filename", "?"), root), type(e).__name__)
    ):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".pytest_cache")]
        for fn in sorted(filenames):
            if fn.startswith("test_") and fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                scan(full, os.path.relpath(full, root))

print(json.dumps({
    "files_scanned": files_scanned,
    "unreadable": unreadable,
    "findings": results,
}, separators=(",", ":")))
