"""A test that hands its assertions to a same-file helper.

detect.py follows the delegation far enough to know the helper asserts, which is why
these are not reported as having no value check. What it never does is judge whether the
helper checks a real value, so they are NOT_ANALYZED: neither cleared nor flagged.
"""
from demo_subject import build_report


def check_report(report):
    assert report["rows"]
    assert report["total"] == sum(r["n"] for r in report["rows"])


# EXPECT: NOT_ANALYZED  (assertions live in check_report)
def test_report_small():
    check_report(build_report([1, 2]))


# EXPECT: NOT_ANALYZED  (delegates through a second helper)
def check_twice(report):
    check_report(report)


def test_report_large():
    check_twice(build_report(list(range(50))))
