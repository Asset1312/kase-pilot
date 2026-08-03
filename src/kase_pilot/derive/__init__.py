"""Derived views rebuilt from the raw stream log.

Everything in this package is re-derivable: it reads the append-only log and
produces an interpretation. If the interpretation turns out to be wrong, the
code changes and the view is rebuilt — the stored raw data is never altered.
"""

from kase_pilot.derive.reconstruct import rebuild_order_book, rebuild_quote

__all__ = ["rebuild_order_book", "rebuild_quote"]
