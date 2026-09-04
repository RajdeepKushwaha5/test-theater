#!/usr/bin/env -S rote play run
/**
 * test-theater
 *
 * Read-only ast audit of a Python test suite: classifies every test function as
 * CANNOT_FAIL (no-assertion, asserts-literal, mock-only, swallowed-exception,
 * no-subject-call), WEAK (permanently-skipped, duplicate-body), or NOT_ANALYZED
 * (unproven — never labeled "good"). Never imports or executes the audited suite;
 * only ast.parse touches it.
 *
 * @rote-frontmatter
 * ---
 * name: test-theater
 * description: "Finds Python tests that cannot fail, without running them. CANNOT_FAIL marks tests whose assertions are all on literals, or are swallowed by a bare except. NO_VALUE_CHECK marks tests with no assertion anywhere. WEAK marks permanently-skipped and duplicate bodies. Everything else is EXAMINED: read, with no pattern matched, which is never a claim the test is good. NOT_ANALYZED is kept for a test that delegates its assertions to a same-file helper: the helper is known to assert, which is why the test is not flagged, but whether it checks a real value was never judged, so the test is neither cleared nor flagged. It is reported separately so a judged-clean suite and an unjudged one cannot look alike. Reads pytest assert, unittest self.assert*, async tests, and assertions delegated to same-file helpers. Every finding carries the commit and age of the line that introduced it; pass base_ref=origin/main for a per-pull-request gate listing only what your branch added. Names any path it could not read, and shows no findings at all when a step was blocked or truncated rather than passing a partial run off as a clean one. Pass target=demo to audit the bundled suite with no repository and no setup. Never imports or executes the suite: only ast.parse touches it. Zero credentials, python3 and git."
 * source_url: https://github.com/RajdeepKushwaha5/test-theater
 * tags:
 * - testing
 * - static-analysis
 * - python
 * - code-quality
 * output:
 *   format: json
 * provenance:
 *   author: rajdeepkushwaha
 * parameters:
 * - name: target
 *   param_type: string
 *   required: true
 *   description: Absolute path to a Python test file or a directory to walk recursively for test_*.py files
 * - name: base_ref
 *   param_type: string
 *   required: false
 *   default: ""
 *   description: Optional git ref such as origin/main. When set, findings are split NEW_IN_BRANCH from PREEXISTING and only what this branch introduced is listed.
 * metadata:
 *   rote_version: 0.78.0
 *   version: 0.8.1
 *   status: released
 *   kind: atomic
 *   flow_type: sequential
 *   execution_model: steps_with_presentation
 *   format: typescript
 *   requires_sessions: false
 *   discoverability:
 *     tags:
 *     - testing
 *     - static-analysis
 *     - python
 * presentation_fixtures:
 *   audit: resources/presentation-fixtures/audit/fixture.yaml
 *   git_dates: resources/presentation-fixtures/git_dates/fixture.yaml
 * steps:
 *   audit:
 *     type: process.exec
 *     timeout_ms: 120000
 *     argv:
 *     - python3
 *     - '@resource{audit_dir.py}'
 *     - $target
 *   git_dates:
 *     type: process.exec
 *     timeout_ms: 60000
 *     depends_on: [audit]
 *     argv:
 *     - python3
 *     - '@resource{git_dates.py}'
 *     - $target
 *     - '@audit{.stdout.text}'
 *     - $base_ref
 * ---
 */

// Presentation plane: deprivileged; imports ONLY the presentation SDK; owns no effects.
const { FlowOutput, loadPresentationContext, stepName } =
  await import("__ROTE_PRESENTATION_SDK__");

const out = new FlowOutput();
const ctx = await loadPresentationContext();

type Git = { status: string; commit?: string; days_ago?: number; date?: string };
type Finding = { test: string | null; verdict: string; reason: string; line: number; file: string; git?: Git; branch_status?: string };

// Every step is inspected, not just the one carrying the payload. A step that was
// blocked, skipped, failed or previewed at rote's 64 KiB ceiling must be named: a
// report built from a partial document is not a shorter report, it is a wrong one.
type Degraded = { step: string; state: string; detail: string };
const degraded: Degraded[] = [];

// Takes the handle, not the name, so every stepName("...") stays a literal lint can verify.
function checkStep(name: string, step: ReturnType<typeof ctx.step>) {
  const o = step.outcome as { status: string; output?: Record<string, unknown> };
  if (o.status !== "completed" && o.status !== "restored") {
    degraded.push({
      step: name,
      state: o.status,
      detail: String(o.output?.reason ?? o.output?.message ?? "no detail recorded"),
    });
    return null;
  }
  return (o.output ?? {}) as { body?: Record<string, unknown> };
}

const auditStep = checkStep("audit", ctx.step(stepName("audit")));
const gitStep = checkStep("git_dates", ctx.step(stepName("git_dates")));

for (const [name, st] of [["audit", auditStep], ["git_dates", gitStep]] as const) {
  if (!st) continue;
  const body = (st.body ?? {}) as { stdout?: { truncated?: boolean; bytes?: number } };
  if (body.stdout?.truncated) {
    degraded.push({
      step: name,
      state: "truncated",
      detail: `stdout was cut at rote's 64 KiB preview ceiling (${body.stdout?.bytes ?? "?"} bytes produced)`,
    });
  }
}

if (degraded.length > 0) {
  const rows = degraded.map((d) => `- ${d.step}: ${d.state} — ${d.detail}`).join("\n");
  out.human(
    `# Audit incomplete\n\nThis run did not produce a usable report, so no findings are shown. Treating a partial run as a clean suite is the exact mistake this play exists to catch.\n\n${rows}`,
  );
  out.summary(`incomplete: ${degraded.map((d) => `${d.step} ${d.state}`).join(", ")}`);
  out.result({ status: "incomplete", degraded, findings: [] });
} else {

const audit = { body: (gitStep!.body ?? {}) } as {
  body: { stdout?: { text?: string } };
};
const stdout = audit.body.stdout?.text;
if (stdout === undefined) throw new Error("git_dates captured no stdout");

let findings: Finding[] = [];
let gitStatus = "unknown";
let totalTests = 0;
let notAnalyzedCount = 0;
let examinedCount: number | null = null;
let baseRef: string | null = null;
let baseRefStatus: string | null = null;
let filesScanned: number | null = null;
let unreadable: { path: string; reason: string }[] = [];
try {
  const parsed = JSON.parse(stdout) as {
    git_status: string; findings: Finding[]; total_tests: number; not_analyzed_count: number; examined_count?: number;
    base_ref: string | null; base_ref_status: string | null;
    files_scanned: number | null; unreadable: { path: string; reason: string }[];
  };
  findings = parsed.findings;
  gitStatus = parsed.git_status;
  totalTests = parsed.total_tests;
  notAnalyzedCount = parsed.not_analyzed_count;
  examinedCount = parsed.examined_count ?? null;
  baseRef = parsed.base_ref;
  baseRefStatus = parsed.base_ref_status;
  filesScanned = parsed.files_scanned;
  unreadable = parsed.unreadable ?? [];
} catch (cause) {
  throw new Error("git_dates stdout was not valid JSON", { cause });
}

const branchMode = baseRef !== null && baseRefStatus === "ok";
const preexisting = branchMode
  ? findings.filter((f) => f.branch_status === "PREEXISTING").length
  : 0;
const indeterminate = branchMode
  ? findings.filter((f) => f.branch_status === "GIT_INDETERMINATE").length
  : 0;
if (branchMode) {
  findings = findings.filter((f) => f.branch_status === "NEW_IN_BRANCH");
}

const unparseable = findings.filter((f) => f.verdict === "UNPARSEABLE");
const cannotFail = findings.filter((f) => f.verdict === "CANNOT_FAIL");
const noValueCheck = findings.filter((f) => f.verdict === "NO_VALUE_CHECK");
const weak = findings.filter((f) => f.verdict === "WEAK");


function row(f: Finding): string {
  const reason = f.reason ? `${f.verdict}/${f.reason}` : f.verdict;
  const g = f.git;
  const age = g && g.status === "ok"
    ? ` — added ${g.date} (${g.days_ago}d ago, ${g.commit})`
    : g && g.status !== "not-blamed"
    ? ` — git: ${g.status}`
    : "";
  return `- ${f.file}:${f.line}${age} \`${f.test ?? "(unparseable)"}\` — ${reason}`;
}

const sections: string[] = [];
if (unparseable.length > 0) {
  sections.push(`## Unparseable (${unparseable.length})\n${unparseable.map(row).join("\n")}`);
}
if (cannotFail.length > 0) {
  sections.push(`## CANNOT_FAIL (${cannotFail.length})\n${cannotFail.map(row).join("\n")}`);
}
if (noValueCheck.length > 0) {
  sections.push(
    `## NO_VALUE_CHECK (${noValueCheck.length})\nFails only if the code raises; never checks a value.\n${noValueCheck.map(row).join("\n")}`,
  );
}
if (weak.length > 0) {
  sections.push(`## WEAK (${weak.length})\n${weak.map(row).join("\n")}`);
}

if (branchMode) {
  sections.push(
    `## Suppressed
${preexisting} finding(s) predate ${baseRef} and are not this branch's doing.` +
      (indeterminate > 0 ? ` ${indeterminate} could not be attributed and are reported as GIT_INDETERMINATE.` : ""),
  );
} else if (baseRef !== null) {
  sections.push(`## Base ref
Could not resolve \`${baseRef}\`, so no branch attribution was made.`);
}

if (unreadable.length > 0) {
  const rows = unreadable.map((u) => `- ${u.path} (${u.reason})`).join("\n");
  sections.push(
    `## Incomplete scan (${unreadable.length} path(s) unreadable)\nThese were not read, so this report is partial and a low finding count does not mean a clean suite.\n${rows}`,
  );
}

const tail: string[] = [];
if (examinedCount === null) {
  // an older observation, before examined and unread were told apart
  tail.push(`## Not analyzed (${notAnalyzedCount} of ${totalTests})
Not proven unfailable. This is not a claim that they are good.`);
} else {
  tail.push(`## Examined, nothing matched (${examinedCount} of ${totalTests})
Read and no theatre pattern matched. Not proven unfailable, and not a claim they are good.`);
  if (notAnalyzedCount > 0) {
    tail.push(`## Not analyzed (${notAnalyzedCount} of ${totalTests})
Assertions live in a same-file helper. That helper does assert, which is why these are not flagged, but whether it checks a real value was never judged. Neither cleared nor flagged.`);
  }
}
if (gitStatus !== "ok") tail.push(`Git join: ${gitStatus}.`);
for (const t of tail) sections.push(t);

const target = ctx.params.target;
out.human(
  [branchMode
    ? `# Test theatre introduced by this branch (vs ${baseRef}): ${findings.length}`
    : `# Unfailable-test audit: ${typeof target === "string" ? target : "target"}`, ...sections].join(
    "\n\n",
  ),
);
out.summary(
  `${totalTests} test(s): ${cannotFail.length} CANNOT_FAIL, ${noValueCheck.length} NO_VALUE_CHECK, ${weak.length} WEAK, ${examinedCount ?? "?"} EXAMINED, ${notAnalyzedCount} NOT_ANALYZED, ${unparseable.length} UNPARSEABLE`,
);
out.result({
  run_id: ctx.run.run_id,
  target,
  flagged: findings.length,
  git_status: gitStatus,
  files_scanned: filesScanned,
  unreadable,
  base_ref: baseRef,
  base_ref_status: baseRefStatus,
  preexisting_count: preexisting,
  cannot_fail: cannotFail,
  no_value_check: noValueCheck,
  weak,
  examined_count: examinedCount,
  not_analyzed_count: notAnalyzedCount,
  total_tests: totalTests,
  unparseable,
});
}
