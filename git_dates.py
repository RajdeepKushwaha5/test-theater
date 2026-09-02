#!/usr/bin/env python3
"""Join ast findings with git blame: when was each flagged test last touched, and in
which commit. Read-only (`git blame` only). Degrades to a labelled unknown -- a target
that is not a git repository, or a file git does not track, never fails the run.

argv[1] = target path that was audited
argv[2] = findings JSON emitted by audit_dir.py
argv[3] = optional base ref (e.g. origin/main). When given, each finding is also
          classified NEW_IN_BRANCH / PREEXISTING by asking whether the commit that
          introduced its line is already an ancestor of that base.
"""
import json, subprocess, sys, time


def rc(args, cwd=None):
    """Exit code only -- used for `merge-base --is-ancestor`, where 0/1 is the answer."""
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True,
                              text=True, timeout=20).returncode
    except Exception:
        return None


def run(args, cwd=None):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def classify_branch(root, findings, base_ref):
    """A finding is PREEXISTING when the commit that introduced its line is already
    reachable from base_ref. Anything we cannot resolve stays GIT_INDETERMINATE --
    never guessed, because "this branch added it" is an accusation."""
    if rc(["git", "-C", root, "rev-parse", "--verify", "--quiet", base_ref + "^{commit}"]) != 0:
        for f in findings:
            f["branch_status"] = "GIT_INDETERMINATE"
        return "unresolved-base-ref"
    seen = {}
    for f in findings:
        g = f.get("git") or {}
        sha = g.get("commit") if g.get("status") == "ok" else None
        if not sha:
            f["branch_status"] = "GIT_INDETERMINATE"
            continue
        if sha not in seen:
            code = rc(["git", "-C", root, "merge-base", "--is-ancestor", sha, base_ref])
            seen[sha] = ("PREEXISTING" if code == 0
                         else "NEW_IN_BRANCH" if code == 1 else "GIT_INDETERMINATE")
        f["branch_status"] = seen[sha]
    return "ok"


def emit(status, root, findings, base_ref=None, branch_status=None):
    """Only flagged findings are enumerated. NOT_ANALYZED is reported as a count:
    listing hundreds of "not analyzed" rows is noise, and the full document would
    exceed the 64 KiB a step's captured stdout carries."""
    flagged = [f for f in findings if f.get("verdict") not in (None, "NOT_ANALYZED")]
    return json.dumps({
        "git_status": status,
        "repo_root": root,
        "base_ref": base_ref or None,
        "base_ref_status": branch_status,
        "total_tests": len(findings),
        "not_analyzed_count": len(findings) - len(flagged),
        "findings": flagged,
    }, separators=(",", ":"))


def main():
    target = sys.argv[1]
    findings = json.loads(sys.argv[2])
    base_ref = sys.argv[3].strip() if len(sys.argv) > 3 else ""

    import os
    base = target if os.path.isdir(target) else os.path.dirname(target)
    root = run(["git", "-C", base, "rev-parse", "--show-toplevel"])

    if root is None:
        for f in findings:
            f["git"] = {"status": "not-a-git-repo"}
        print(emit("not-a-git-repo", None, findings))
        return

    # A shallow clone can only attribute every line to the one commit it has, which
    # would report a uniform, meaningless age. Say so instead of inventing history.
    if run(["git", "-C", root, "rev-parse", "--is-shallow-repository"]) == "true":
        for f in findings:
            f["git"] = {"status": "shallow-clone"}
        print(emit("shallow-clone", root, findings))
        return

    now = time.time()
    cache = {}
    for f in findings:
        # only the flagged ones are worth a blame call
        if f.get("verdict") in (None, "NOT_ANALYZED"):
            f["git"] = {"status": "not-blamed"}
            continue
        rel = os.path.join(base, f.get("file", ""))
        key = (rel, f.get("line"))
        if key in cache:
            f["git"] = cache[key]
            continue
        line = f.get("line") or 1
        out = run(["git", "-C", root, "blame", "-L", "%d,%d" % (line, line),
                   "--porcelain", "--", rel])
        if not out:
            info = {"status": "unknown"}
        else:
            head = out.splitlines()[0].split()
            sha = head[0][:8] if head else None
            ts = None
            for ln in out.splitlines():
                if ln.startswith("author-time "):
                    ts = int(ln.split()[1]); break
            if sha and ts:
                info = {"status": "ok", "commit": sha,
                        "days_ago": int((now - ts) // 86400),
                        "date": time.strftime("%Y-%m-%d", time.gmtime(ts))}
            else:
                info = {"status": "unknown"}
        cache[key] = info
        f["git"] = info

    branch_status = classify_branch(root, findings, base_ref) if base_ref else None
    print(emit("ok", root, findings, base_ref, branch_status))


if __name__ == "__main__":
    main()
