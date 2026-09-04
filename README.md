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
| `NOT_ANALYZED` | Not proven unfailable. **This is not a claim that the test is good.** |

The last row is the point. A tool that reports good news teaches people to skim it,
and a confident wrong "safe" is worse than no tool at all.

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
python3 detect.py fixtures/tests/test_calc.py
python3 detect.py fixtures/tests/test_styles.py
```

Each fixture test carries a `# EXPECT:` comment stating the verdict it must receive.
All 16 match.

## On real codebases

Four public repositories, no execution, `python3` + `git` only:

| repo | tests | flagged |
|---|---:|---:|
| psf/requests | 347 | 11 |
| pallets/flask | 372 | 3 |
| pallets/click | 538 | 7 |
| boto/boto3 | 444 | 1 |

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

## Licence

MIT
