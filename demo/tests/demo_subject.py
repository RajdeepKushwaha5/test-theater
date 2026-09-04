"""Subject under test for the bundled demo. Never imported by the play: only read."""


def build_report(values):
    rows = [{"n": v} for v in values]
    return {"rows": rows, "total": sum(values)}
