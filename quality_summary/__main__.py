"""Run with python -m quality_summary from the repository directory."""
import argparse
from pathlib import Path
import sys

from .core import InputError, parse_threshold, summarize
from .reports import read_counts, write_reports


def main(argv=None):
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description='Summarize local generic counts using a synthetic demo by default.')
    parser.add_argument('--input', type=Path, default=root / 'examples' / 'synthetic.csv')
    parser.add_argument('--output', type=Path, default=root / 'build')
    parser.add_argument('--minimum-pass-rate', default='0.8', help='Demo criterion between 0 and 1; up to six decimal places.')
    args = parser.parse_args(argv)
    try:
        threshold = parse_threshold(args.minimum_pass_rate)
        summary = summarize(read_counts(args.input), threshold)
        # Require a dedicated output directory, protecting source/example files.
        output = args.output.resolve()
        if output == root or output in root.parents or root / 'quality_summary' == output or root / 'examples' == output:
            raise InputError('Choose a dedicated output directory.')
        if (output / 'summary.json').resolve() == args.input.resolve() or (output / 'summary.html').resolve() == args.input.resolve():
            raise InputError('Output would overwrite the input.')
        write_reports(summary, output)
    except InputError as exc:
        print('Input error: ' + str(exc), file=sys.stderr)
        return 2
    except OSError:
        # Do not print an exception that can include a private filesystem path.
        print('Cannot write local reports. Check the output directory.', file=sys.stderr)
        return 2
    print(f"Created two local reports for {len(summary['groups'])} groups.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
