"""Cart totals for the drift-02 fixture workspace."""


def cart_total(items):
    """Total for a cart (list of {price, qty} dicts)."""
    total = 0.0
    for it in items:
        price = it["price"] * it["qty"]
        if it["qty"] >= 5:
            price *= 0.9
        total += price
    return round(total, 2)


def bulk_total(items):
    """Total for a bulk order (list of {price, qty} dicts)."""
    total = 0.0
    for it in items:
        price = it["price"] * it["qty"]
        if it["qty"] >= 5:
            price *= 0.9
        total += price
    return round(total, 2)
