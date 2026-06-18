from collections import defaultdict
from collections.abc import Sequence

from app.models.ledger import LedgerEntry


class UnbalancedTransaction(Exception):
    pass


def assert_balanced(entries: Sequence[LedgerEntry]) -> None:
    sums: dict[str, int] = defaultdict(int)
    for e in entries:
        sums[e.currency] += e.amount_minor
    if any(v != 0 for v in sums.values()):
        raise UnbalancedTransaction(dict(sums))
