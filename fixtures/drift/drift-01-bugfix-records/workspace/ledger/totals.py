"""Invoice totals for the drift-01 fixture workspace."""


def total(amounts):
    """Return the total of all line amounts."""
    # BUG: drops the last line.
    return sum(amounts[:-1])


def total_with_tax(amounts, rate=0.0):
    """Return the total including tax at `rate` (e.g. 0.08)."""
    return round(total(amounts) * (1.0 + rate), 2)
