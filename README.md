# test-theater

**Which of your tests can never fail?**

An AI assistant writes 200 tests. Coverage goes up, CI stays green, and nobody can
say which of those assertions would actually object if the code returned the wrong
answer. `test-theater` finds the ones that provably wouldn't — by parsing the suite,
never by running it.

```bash
rote play run https://play.modiqo.ai/rajdeepkushwaha/test-theater target=./tests
```

Zero credentials. Never imports or executes the suite under audit: only `ast.parse`
touches it. Needs `python3` and `git`.

Every finding carries the commit and age of the line that introduced it, so recently
added theatre is separable from decade-old decisions:

```
test_packages.py:4  — added 2017-05-29 (3382d ago, 1278ecdf)
  `test_can_access_urllib3_attribute` — NO_VALUE_CHECK/no-assertion
```

A shallow clone is reported as `shallow-clone` rather than given a uniform,
meaningless date, and a target outside a repository is reported as `not-a-git-repo`.
Neither fails the run.

## Try it with nothing set up

```bash
rote play run https://play.modiqo.ai/rajdeepkushwaha/test-theater target=demo
```

That audits a suite bundled with the play, so there is nothing to clone and no repository
to point at. It shows all five verdicts, including `NOT_ANALYZED`, which the fixtures alone
never produced. There is no git history in a bundled directory, so the git join reports
`not-a-git-repo` rather than pretending to dates it does not have.

## Use it as a pull-request gate

```bash
rote play run https://play.modiqo.ai/rajdeepkushwaha/test-theater   target=./tests base_ref=origin/main
```

With `base_ref` set, findings are split by whether the commit that introduced the line
is already reachable from that ref:

```
# Test theatre introduced by this branch (vs origin/main): 1

## NO_VALUE_CHECK (1)
- test_config.py:253 — added 2026-09-02 (0d ago, f97d4b4a)
  `test_new_config_thing` — NO_VALUE_CHECK/no-assertion

## Suppressed
3 finding(s) predate origin/main and are not this branch's doing.
```

Anything that cannot be attributed stays `GIT_INDETERMINATE` rather than being blamed on
the branch. An unresolvable ref falls back to a whole-repository audit and says so.


## Verdicts

| verdict | what is being claimed |
|---|---|
| `CANNOT_FAIL` | Provably cannot fail. Every assertion is on literals (`assert 1 == 1`), or the assertion is swallowed by a bare `except: pass`. |
| `NO_VALUE_CHECK` | Fails only if the code *raises*. No assertion anywhere — not in the test, not in a helper it calls. |
| `WEAK` | Permanently skipped, or a byte-identical duplicate of another test body. |
| `EXAMINED` | Read, and no pattern matched. Not proven unfailable, and **not a claim the test is good.** |
| `NOT_ANALYZED` | Assertions live in a same-file helper. That helper *does* assert, which is why the test is not flagged, but whether it checks a real value was never judged. Neither cleared nor flagged. |

The last two rows used to be one row, and that was a defect. Everything that was not
flagged came back `NOT_ANALYZED`, which reads as "the tool failed to look" for tests it had
in fact read and found clean. Worse, it hid the tests it genuinely could not read inside
the same bucket.

Across four public suites that bucket held 1,273 tests. **1,263 had been examined and judged
clean. 10 were never judged at all**, all in flask, and they were invisible among 369 rows
in the same section. A clean suite and an unread one are now impossible to confuse.

## It refuses to report on a partial run

Every step is inspected, not just the one carrying the payload. If a step was blocked,
skipped, failed, or cut at rote's 64 KiB stdout preview ceiling, no findings are shown
and the reason is named:

```
# Audit incomplete

This run did not produce a usable report, so no findings are shown. Treating a
partial run as a clean suite is the exact mistake this play exists to catch.

- audit: truncated - stdout was cut at rote's 64 KiB preview ceiling (100577 bytes produced)
```

Six negative cases ship with the package (partial, truncated and blocked per step) and
are replayed by `play audit rehearse`. All six pass. Replacing the presentation body with
a constant makes all six fail, which is how I know the pass means something.

## It tells you what it could not read

`os.walk` skips directories it cannot open, in silence. That turns a permissions problem
into a shorter, cleaner-looking report, which is the same defect this tool exists to find:

```
## Incomplete scan (1 path(s) unreadable)
These were not read, so this report is partial and a low finding count does not
mean a clean suite.
- locked (PermissionError)
```

A file it cannot open or decode is named too, rather than dropped. When everything was
readable the section does not appear at all.

## What it deliberately does not do

It does **not** measure whether the surviving tests would catch a real defect. That
needs mutation testing — running the suite once per injected fault — and it is a
different, much slower tool. `test-theater` answers the cheap half of the question
in seconds, statically.

It recognises pytest `assert`, `unittest` `self.assert*`, and `async def` tests.
A `no-subject-call` detector was built and **removed**: it fired on every
fixture-based test, which is most of them, and could not be made sound without
dataflow analysis.

## Verify it

```bash
python3 verify-fixtures.py
# 16 expectation(s), 0 mismatch(es)

python3 verify-contract.py
# 9 field(s) checked, all emitted
```

Each fixture test carries a `# EXPECT:` comment stating the verdict it must receive, and
that script checks every one of them, exiting non-zero on a mismatch.

`verify-contract.py` checks the other seam. The producers are Python and the presentation
is TypeScript, so nothing type-checks between them: a field renamed on the Python side
arrives in TypeScript as `undefined` and renders as a blank, not an error. The script reads
every `parsed.<field>` the presentation touches, runs the producers on the bundled demo, and
fails if any is missing. Renaming `examined_count` to `examined_kount` in a scratch copy is
caught, exit code 1.

The fixture checker exists because the sentence that used to sit here — "all 16 match" — was false. When the
`mock-only` rule was removed as a false positive, `test_service_called` stopped matching its
expectation and nothing noticed, because the claim was prose. `svc.fetch.assert_called_once_with(3)`
does check a value, so `EXAMINED` was the right answer and the comment was the stale part.

## On real codebases

Four public repositories, no execution, `python3` + `git` only:

Measured on clean upstream trees, pinned so you can reproduce them:

| repo | commit | tests | flagged | examined | not analyzed |
|---|---|---:|---:|---:|---:|
| psf/requests | `5460f467` | 347 | 11 | 336 | 0 |
| pallets/flask | `d318b683` | 372 | 3 | 359 | 10 |
| pallets/click | `36baa15` | 538 | 7 | 531 | 0 |
| boto/boto3 | `81ae0477` | 562 | 8 | 495 | 59 |

Getting there meant removing **seven** false-positive classes, each found by running
against code the author did not write:

1. `import X` module tracking (only `from X import` was followed)
2. typed `except` handlers read as swallowed assertions
3. `skipif` inside `@parametrize` marks read as a permanent skip
4. `pytest.fail()` counted as a literal assertion
5. `no-subject-call` — removed entirely; unsound for every fixture-based test
6. functions merely *nested* inside a test (route handlers, CLI commands named `test`)
7. assertions delegated to a same-file helper, and `mock.assert_called_with` — which
   does check values, so claiming otherwise was simply wrong

Across those four repos that took the raw output from **200 findings to 22**. The
survivors are genuine: three tests in `requests` that make a real call and assert
nothing, dating from 2017.

```
test_packages.py:4 — added 2017-05-29 (3382d ago, 1278ecdf)
  `test_can_access_urllib3_attribute` — NO_VALUE_CHECK/no-assertion
```

Every removal made the tool claim *less*. That is the point: a confident wrong
"this test is worthless" costs a reviewer more than silence.

## boto3 used to fail outright

The `audit` step emitted a row per test. On boto3 that came to **70,121 bytes**, past
rote's 64 KiB stdout preview ceiling, so the next step received truncated JSON and the run
died. The play failed *safely* — it refuses to show findings from a partial run, which is
the whole design — but "safely unusable" is still unusable, and the number published here
for boto3 had been measured back when the suite was small enough to fit.

Only flagged rows travel between steps now, with the rest carried as counts. Same suite,
same information: **1,212 bytes**. This is the third time the same lesson has come up in
this play, after the git-blame join and the whole-repo enumeration: never move a row when a
count will do.

## Licence

MIT
