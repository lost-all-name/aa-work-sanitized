"""Pure aggregation: every group follows the same caller-selected criterion."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


class InputError(ValueError):
    """A user-facing validation error without input contents."""


@dataclass(frozen=True)
class Count:
    group: str
    total: int
    passed: int

    def __post_init__(self):
        if not isinstance(self.group, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', self.group):
            raise InputError('group must be a short lowercase identifier.')
        if type(self.total) is not int or type(self.passed) is not int:
            raise InputError('total and passed must be integers.')
        if not 1 <= self.total <= 10**12 or not 0 <= self.passed <= self.total:
            raise InputError('Counts must satisfy 0 <= passed <= total, with total between 1 and 10^12.')


def parse_threshold(value):
    try:
        threshold = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise InputError('minimum pass rate must be a decimal between 0 and 1.') from None
    if not threshold.is_finite() or not 0 <= threshold <= 1:
        raise InputError('minimum pass rate must be a decimal between 0 and 1.')
    # Bound precision to keep comparisons independent of Decimal context rounding.
    if threshold.as_tuple().exponent < -6:
        raise InputError('minimum pass rate supports up to six decimal places.')
    return threshold


def summarize(counts, minimum_pass_rate=Decimal('0.8')):
    """Aggregate counts, then compare each aggregate to a single demo criterion.

    The default criterion is chosen for the bundled synthetic example only.
    It is not a production recommendation or an industry standard.
    """
    threshold = parse_threshold(minimum_pass_rate)
    grouped = {}
    record_count = 0
    for count in counts:
        if not isinstance(count, Count):
            raise InputError('Expected validated Count records.')
        record_count += 1
        if record_count > 100_000:
            raise InputError('Input supports up to 100000 records.')
        current = grouped.setdefault(count.group, [0, 0])
        current[0] += count.total
        current[1] += count.passed
    if not grouped:
        raise InputError('Input must contain at least one record.')

    def result(group, total, passed):
        # Convert the finite decimal criterion into an exact integer comparison.
        numerator, denominator = threshold.as_integer_ratio()
        return {
            'group': group,
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': format(Decimal(passed) / Decimal(total), '.6f'),
            'meets_criterion': passed * denominator >= total * numerator,
        }

    groups = [result(group, *grouped[group]) for group in sorted(grouped)]
    total = sum(row['total'] for row in groups)
    passed = sum(row['passed'] for row in groups)
    return {
        'schema_version': 1,
        'record_count': record_count,
        'minimum_pass_rate': format(threshold, 'f'),
        'overall': result('overall', total, passed),
        'groups': groups,
    }
