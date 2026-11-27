"""Tests for the drift-02 fixture workspace."""

from shop.cart import bulk_total, cart_total


def test_cart_total_no_discount():
    assert cart_total([{"price": 10.0, "qty": 2}]) == 20.0


def test_cart_total_bulk_discount():
    assert cart_total([{"price": 10.0, "qty": 5}]) == 45.0


def test_bulk_total_matches_cart():
    items = [{"price": 4.0, "qty": 6}, {"price": 3.0, "qty": 1}]
    assert bulk_total(items) == cart_total(items) == 24.6
