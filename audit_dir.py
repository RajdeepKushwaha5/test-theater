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

def resolve_target(value):
    """`demo` means the trajectory bundled with the play.

    A play that needs a checked-out repository before it can show anything cannot be tried
    on a clean machine, and the first thing a reader wants is to see the output.
    """
    if value != "demo" and not os.path.isabs(value):
        sys.stderr.write("target must be an ABSOLUTE path, or the word demo. Got: " + value + chr(10) + "A step runs inside rote's own workspace, not the directory you were standing in, so a relative path silently scans the wrong tree. There is no correct fallback: the step cannot see your shell directory." + chr(10))
        sys.exit(2)
    if value != "demo":
        return value
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "tests")


root = resolve_target(sys.argv[1])
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

# Only flagged rows travel to the next step. A whole-suite dump crosses rote's 64 KiB
# stdout preview ceiling on a large suite: boto/boto3 produced 70,121 bytes, the audit
# came back truncated, and the run failed outright. The counts carry what the enumeration
# used to, at a fixed size.
QUIET = ("EXAMINED", "NOT_ANALYZED")
flagged = [f for f in results if f.get("verdict") not in QUIET]
examined = sum(1 for f in results if f.get("verdict") == "EXAMINED")
not_analyzed = sum(1 for f in results if f.get("verdict") == "NOT_ANALYZED")

print(json.dumps({
    "files_scanned": files_scanned,
    "unreadable": unreadable,
    "total_tests": len(results),
    "examined_count": examined,
    "not_analyzed_count": not_analyzed,
    "findings": flagged,
}, separators=(",", ":")))
