from decimal import Decimal
import unittest

from quality_summary.core import Count, InputError, parse_threshold, summarize


class SummaryTests(unittest.TestCase):
    def test_combines_same_group_and_sorts_names(self):
        summary = summarize([Count('b', 3, 1), Count('a', 4, 3), Count('b', 2, 2)])
        self.assertEqual([row['group'] for row in summary['groups']], ['a', 'b'])
        self.assertEqual(summary['groups'][1]['total'], 5)
        self.assertEqual(summary['groups'][1]['passed'], 3)
        self.assertEqual(summary['overall']['total'], 9)
        self.assertEqual(summary['overall']['passed'], 6)
        self.assertEqual(summary['overall']['failed'], 3)

    def test_overall_rate_is_weighted_by_counts(self):
        summary = summarize([Count('a', 1, 0), Count('b', 99, 99)])
        self.assertEqual(summary['overall']['pass_rate'], '0.990000')

    def test_criterion_is_inclusive(self):
        self.assertTrue(summarize([Count('a', 5, 4)])['groups'][0]['meets_criterion'])

    def test_rounding_does_not_change_decision(self):
        row = summarize([Count('a', 1_000_000_000, 799_999_999)])['groups'][0]
        self.assertEqual(row['pass_rate'], '0.800000')
        self.assertFalse(row['meets_criterion'])

    def test_zero_and_one_criteria(self):
        self.assertTrue(summarize([Count('a', 2, 0)], 0)['overall']['meets_criterion'])
        self.assertTrue(summarize([Count('a', 2, 2)], 1)['overall']['meets_criterion'])
        self.assertFalse(summarize([Count('a', 2, 1)], 1)['overall']['meets_criterion'])

    def test_rejects_invalid_counts(self):
        for total, passed in [(0, 0), (-1, 0), (1, 2), (1, -1), (True, 0), (2, 1.0), (10**12 + 1, 0)]:
            with self.subTest(total=total, passed=passed), self.assertRaises(InputError):
                Count('a', total, passed)

    def test_rejects_free_text_and_formula_group_names(self):
        for group in ['', 'Capital', 'contains space', '=1+1', '<tag>', 'a' * 41, None]:
            with self.subTest(group=group), self.assertRaises(InputError):
                Count(group, 2, 1)

    def test_rejects_nonfinite_or_out_of_range_criteria(self):
        for value in ['NaN', 'Infinity', '-0.1', '1.1', 'invalid', '0.1234567']:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_threshold(value)

    def test_accepts_six_decimal_places_and_scientific_notation(self):
        self.assertEqual(parse_threshold('1e-6'), Decimal('0.000001'))

    def test_rejects_empty_and_unvalidated_records(self):
        for records in [[], [{'group': 'a', 'total': 2, 'passed': 1}]]:
            with self.assertRaises(InputError):
                summarize(records)

    def test_record_limit_is_enforced_for_generators(self):
        with self.assertRaises(InputError):
            summarize(Count('a', 1, 1) for _ in range(100_001))


if __name__ == '__main__':
    unittest.main()
