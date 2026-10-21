from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from quality_summary.__main__ import main


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, args):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(args)
        return code, output.getvalue(), error.getvalue()

    def test_default_input_is_self_contained_synthetic_data(self):
        output = self.root / 'report'
        code, console, error = self.run_cli(['--output', str(output)])
        self.assertEqual(code, 0, error)
        data = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual((data['record_count'], data['overall']['total'], data['overall']['passed']), (4, 92, 78))
        self.assertEqual(len(data['groups']), 3)
        self.assertNotIn(str(output), console)

    def test_threshold_changes_the_demo_decision(self):
        output = self.root / 'report'
        code, _, error = self.run_cli(['--output', str(output), '--minimum-pass-rate', '1'])
        self.assertEqual(code, 0, error)
        data = json.loads((output / 'summary.json').read_text())
        self.assertFalse(any(row['meets_criterion'] for row in data['groups']))

    def test_invalid_input_produces_no_reports(self):
        path = self.root / 'input.csv'
        path.write_text('group,total,passed\nprivate_sample,2,3\n')
        output = self.root / 'report'
        code, console, error = self.run_cli(['--input', str(path), '--output', str(output)])
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())
        self.assertNotIn('private_sample', console + error)

    def test_invalid_criterion_is_rejected_without_output(self):
        output = self.root / 'report'
        code, _, _ = self.run_cli(['--output', str(output), '--minimum-pass-rate', 'NaN'])
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_repository_root_cannot_be_output_directory(self):
        project = Path(__file__).resolve().parents[1]
        code, _, _ = self.run_cli(['--output', str(project)])
        self.assertEqual(code, 2)
        self.assertFalse((project / 'summary.json').exists())


if __name__ == '__main__':
    unittest.main()
