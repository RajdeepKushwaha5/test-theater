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

## Verdicts

| verdict | what is being claimed |
|---|---|
| `CANNOT_FAIL` | Provably cannot fail. Every assertion is on literals (`assert 1 == 1`), or the assertion is swallowed by a bare `except: pass`. |
| `NO_VALUE_CHECK` | Fails only if the code *raises*. Never checks a value — no assertion at all, or only that a mock was called. |
| `WEAK` | Permanently skipped, or a byte-identical duplicate of another test body. |
| `NOT_ANALYZED` | Not proven unfailable. **This is not a claim that the test is good.** |

The last row is the point. A tool that reports good news teaches people to skim it,
and a confident wrong "safe" is worse than no tool at all.

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

## On a real codebase

Run against [`psf/requests`](https://github.com/psf/requests) — 347 test functions,
zero execution:

```
347 tests → 12 NO_VALUE_CHECK · 1 WEAK · 334 NOT_ANALYZED   (705ms)
```

The git join makes the result readable: every finding in `requests` dates from 2012
to 2023. This is a legacy suite, not AI bloat — which is exactly the distinction the
ages exist to draw.

Including three in requests' own suite that make a real call and assert nothing:

```
test_can_access_urllib3_attribute   NO_VALUE_CHECK/no-assertion   test_packages.py:4
test_can_access_idna_attribute      NO_VALUE_CHECK/no-assertion   test_packages.py:8
test_can_access_chardet_attribute   NO_VALUE_CHECK/no-assertion   test_packages.py:12
```

Getting to 13 trustworthy findings took removing four false-positive classes first:
`import X` module tracking, typed `except` handlers being read as swallowed
assertions, `skipif` inside `@parametrize` marks, and `pytest.fail()` being counted
as a literal assertion.

## Licence

MIT
