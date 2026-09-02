"""Tiny subject under test."""

def add(a, b):
    return a + b

def is_even(n):
    return n % 2 == 0

def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value
