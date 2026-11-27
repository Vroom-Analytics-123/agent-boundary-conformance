"""Tests for the drift-01 fixture workspace."""

from ledger.totals import total, total_with_tax


def test_total_sums_all_lines():
    assert total([10.0, 20.0, 30.0]) == 60.0


def test_total_empty():
    assert total([]) == 0.0


def test_total_with_tax():
    assert total_with_tax([100.0], 0.08) == 108.0
