import json
from pathlib import Path
import tempfile
import unittest

from quality_summary.core import Count, InputError, summarize
from quality_summary.reports import read_counts, render_html, write_reports


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def read_text(self, text):
        path = self.root / 'synthetic.csv'
        path.write_text(text, encoding='utf-8-sig')
        return list(read_counts(path))

    def test_reads_synthetic_schema_with_bom(self):
        self.assertEqual(self.read_text('group,total,passed\na,3,2\n'), [Count('a', 3, 2)])

    def test_requires_exact_schema(self):
        for header in ['name,total,passed', 'group,passed,total', 'group,total,passed,extra']:
            with self.subTest(header=header), self.assertRaises(InputError):
                self.read_text(header + '\na,3,2\n')

    def test_rejects_missing_extra_and_invalid_fields(self):
        for row in ['a,3', 'a,3,2,extra', 'a,3.0,2', 'a,3e2,2', 'a,-3,2', '=1+1,3,2', 'a,3,4']:
            with self.subTest(row=row), self.assertRaises(InputError):
                self.read_text('group,total,passed\n' + row + '\n')

    def test_error_does_not_echo_supplied_identifier(self):
        with self.assertRaises(InputError) as result:
            self.read_text('group,total,passed\nPRIVATE INPUT EXAMPLE,2,1\n')
        self.assertNotIn('PRIVATE INPUT EXAMPLE', str(result.exception))

    def test_missing_file_error_does_not_echo_path(self):
        with self.assertRaises(InputError) as result:
            list(read_counts(self.root / 'private_path_marker.csv'))
        self.assertNotIn('private_path_marker', str(result.exception))

    def test_invalid_encoding_is_a_validation_error(self):
        path = self.root / 'bad.csv'
        path.write_bytes(b'\xff\xfe\x00')
        with self.assertRaises(InputError):
            list(read_counts(path))

    def test_html_escapes_all_dynamic_text(self):
        summary = summarize([Count('a', 2, 1)])
        summary['groups'][0]['group'] = '<img src=x onerror=alert(1)>'
        html = render_html(summary)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<img', html)
        self.assertIn("default-src 'none'", html)
        self.assertNotIn('<script', html)

    def test_writes_only_two_expected_outputs(self):
        summary = summarize([Count('a', 2, 1)])
        output = self.root / 'output'
        write_reports(summary, output)
        self.assertEqual({path.name for path in output.iterdir()}, {'summary.json', 'summary.html'})
        self.assertEqual(json.loads((output / 'summary.json').read_text(encoding='utf-8')), summary)


if __name__ == '__main__':
    unittest.main()
