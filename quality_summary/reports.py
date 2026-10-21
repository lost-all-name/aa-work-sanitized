"""Strict generic CSV input and local JSON/HTML output."""
import csv
from html import escape
import json
from pathlib import Path

from .core import Count, InputError


def read_counts(path):
    """Read this demo's own schema; never infer production column mappings."""
    try:
        with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != ['group', 'total', 'passed']:
                raise InputError('CSV header must be exactly: group,total,passed')
            for row_number, row in enumerate(reader, 2):
                if row_number > 100_001:
                    raise InputError('Input supports up to 100000 records.')
                if None in row or any(value is None for value in row.values()):
                    raise InputError(f'CSV record {row_number}: expected exactly three fields.')
                values = {key: value.strip() for key, value in row.items()}
                if any(not value.isascii() or not value.isdecimal() for value in (values['total'], values['passed'])):
                    raise InputError(f'CSV record {row_number}: counts must be unsigned integers.')
                try:
                    count = Count(values['group'], int(values['total']), int(values['passed']))
                except (ValueError, InputError):
                    raise InputError(f'CSV record {row_number}: invalid group or counts.') from None
                yield count
    except (OSError, UnicodeError, csv.Error):
        raise InputError('Cannot read a valid UTF-8 CSV input.') from None


def render_html(summary):
    """A self-contained static report, with no script, links or external assets."""
    def row_html(row):
        status = 'Meets demo criterion' if row['meets_criterion'] else 'Below demo criterion'
        cells = [row['group'], row['total'], row['passed'], row['failed'], row['pass_rate'], status]
        return '<tr>' + ''.join('<td>' + escape(str(value), quote=True) + '</td>' for value in cells) + '</tr>'

    rows = ''.join(row_html(row) for row in [summary['overall'], *summary['groups']])
    criterion = escape(str(summary['minimum_pass_rate']), quote=True)
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Local count summary</title>
<style>
body{font:16px system-ui,sans-serif;background:#f3f5f8;color:#182335;margin:0;padding:32px}
main{max-width:1000px;margin:auto;background:white;border:1px solid #dbe0e8;border-radius:12px;padding:28px;overflow:auto}
h1{font-size:28px;margin:0 0 12px}p{line-height:1.6;color:#42526a}
table{border-collapse:collapse;width:100%;margin-top:24px}th,td{text-align:left;padding:12px;border-bottom:1px solid #dbe0e8}
th{background:#edf1f7}tbody tr:first-child{font-weight:600}caption{text-align:left;margin-bottom:12px}
</style></head><body><main><h1>Local count summary</h1>
<p>Generic groups share one demonstration criterion. Minimum pass rate: ''' + criterion + '''.</p>
<p>Rates are displayed to six decimal places; decisions use exact counts. This report contains the input group identifiers and counts.</p>
<table><caption>Overall and grouped results</caption><thead><tr><th>Group</th><th>Total</th><th>Passed</th><th>Failed</th><th>Pass rate</th><th>Result</th></tr></thead><tbody>''' + rows + '''</tbody></table>
</main></body></html>
'''


def write_reports(summary, output_directory):
    output = Path(output_directory)
    # Outputs are complete only after input parsing and aggregation have succeeded.
    json_text = json.dumps(summary, ensure_ascii=False, indent=2) + '\n'
    html_text = render_html(summary)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json_text, encoding='utf-8')
    (output / 'summary.html').write_text(html_text, encoding='utf-8')
