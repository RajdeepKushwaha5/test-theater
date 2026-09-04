"""Fixture: unittest-style and async-style suites."""
import unittest
from src.calc import add, is_even


class CalcTests(unittest.TestCase):
    # EXPECT: EXAMINED  (genuine unittest assertion — must NOT be CANNOT_FAIL)
    def test_add_two_numbers(self):
        self.assertEqual(add(2, 3), 5)

    # EXPECT: EXAMINED  (assertTrue on a real call)
    def test_even_number(self):
        self.assertTrue(is_even(8))

    # EXPECT: NO_VALUE_CHECK / no-assertion
    def test_placeholder(self):
        pass

    # EXPECT: CANNOT_FAIL / asserts-literal (unittest literal-only)
    def test_local_math(self):
        self.assertEqual(2 + 2, 4)


# EXPECT: EXAMINED  (async test with a real assertion)
async def test_async_add():
    assert add(1, 1) == 2


# EXPECT: NO_VALUE_CHECK / no-assertion
async def test_async_noop():
    add(1, 1)
