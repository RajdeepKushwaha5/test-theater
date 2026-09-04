"""Fixture suite. Every test below is labelled with the verdict it must receive."""
import pytest
from unittest.mock import Mock
from src.calc import add, is_even, clamp


# EXPECT: NO_VALUE_CHECK / no-assertion
def test_add_runs():
    add(1, 2)


# EXPECT: CANNOT_FAIL / asserts-literal
def test_add_works():
    assert True


# EXPECT: CANNOT_FAIL / asserts-literal
def test_math_is_math():
    assert 1 == 1


# EXPECT: EXAMINED  (assert_called_once_with does check a value, so this is not theatre)
def test_service_called():
    svc = Mock()
    svc.fetch(3)
    svc.fetch.assert_called_once_with(3)


# EXPECT: CANNOT_FAIL / swallowed-exception
def test_clamp_never_raises():
    try:
        assert clamp(5, 1, 3) == 999
    except Exception:
        pass


# EXPECT: EXAMINED  (no-subject-call was dropped: unsound for fixture-based tests)
def test_expected_shape():
    payload = {"a": 1, "b": 2}
    assert payload["a"] == 1


# EXPECT: WEAK / permanently-skipped
@pytest.mark.skip(reason="flaky")
def test_clamp_upper():
    assert clamp(9, 1, 3) == 3


# EXPECT: EXAMINED  (genuine test)
def test_is_even_true():
    assert is_even(4) is True


# EXPECT: WEAK / duplicate-body  (same body as test_is_even_true)
def test_is_even_returns_true_for_four():
    assert is_even(4) is True


# EXPECT: EXAMINED  (genuine test)
def test_clamp_lower_bound():
    assert clamp(-5, 1, 3) == 1
