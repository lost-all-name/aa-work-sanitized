"""Build a deterministic public source archive from an explicit file inventory."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = frozenset({
    '.gitattributes', '.gitignore', '.github/workflows/check.yml',
    'LICENSE', 'README.md', 'PRIVACY.md',
    'quality_summary/__init__.py', 'quality_summary/__main__.py',
    'quality_summary/core.py', 'quality_summary/reports.py',
    'examples/synthetic.csv', 'tools/release.py',
    'tests/test_core.py', 'tests/test_reports.py', 'tests/test_cli.py', 'tests/test_release.py',
})
GENERATED = {'build', 'dist', '__pycache__', '.git', '.venv', 'venv'}
EXAMPLE_SHA256 = 'b6f4797548f91779019dbf4438ace710b812f83b08e2d405f48bcd201f097c11'
APP_IMPORTS = {'argparse', 'pathlib', 'sys', 'dataclasses', 'decimal', 're', 'csv', 'html', 'json', 'core', 'reports'}
RULES = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'service token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})'),
    'literal credential': re.compile(r'''(?i)(?:password|passwd|secret|api_key|access_token)\s*[:=]\s*['"][A-Za-z0-9_+/-]{8,}['"]'''),
    'email address': re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    'literal network address': re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])'),
    'server URL': re.compile(r'(?:https?|ftp|wss?)://[A-Za-z0-9\[]'),
    'local user path': re.compile(r'(?i)(?:[a-z]:[\\/]+Users[\\/]+[a-z0-9_.-]+|/(?:home|Users)/[a-z0-9_.-]+)'),
}


class ReleaseError(ValueError):
    pass


def make_manifest(snapshot):
    return {
        'format_version': 1,
        'example_data': 'synthetic',
        'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(snapshot.items())],
    }


def inspect_content(name, data):
    """Report labels only, never an offending credential or source excerpt."""
    findings = []
    if name == 'examples/synthetic.csv' and hashlib.sha256(data).hexdigest() != EXAMPLE_SHA256:
        findings.append('bundled synthetic data changed')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return ['non-UTF-8 payload']
    if '\x00' in text:
        findings.append('binary content')
    findings.extend(label for label, rule in RULES.items() if rule.search(text))
    if name.startswith('quality_summary/') and name.endswith('.py'):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return findings + ['invalid Python']
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or '').split('.')[0]]
            if any(module not in APP_IMPORTS for module in modules):
                findings.append('application import outside offline allowlist')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'eval', 'exec', '__import__', 'compile'}:
                findings.append('dynamic code execution')
    return sorted(set(findings))


def source_snapshot(root=ROOT):
    root = Path(root).resolve()
    inventory = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in GENERATED]
        for name in [*dirs, *files]:
            path = Path(directory) / name
            attrs = getattr(path.lstat(), 'st_file_attributes', 0)
            if path.is_symlink() or attrs & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
                raise ReleaseError('Links and filesystem redirections are not allowed in source.')
        inventory.update((Path(directory) / name).relative_to(root).as_posix() for name in files)
    has_manifest = 'RELEASE_MANIFEST.json' in inventory
    inventory.discard('RELEASE_MANIFEST.json')
    if inventory != FILES:
        missing, extra = sorted(FILES - inventory), sorted(inventory - FILES)
        # Only names are printed; never read unknown files.
        raise ReleaseError(f'File inventory mismatch; missing={missing}; unexpected={extra}')
    snapshot = {}
    for name in sorted(FILES):
        path = root / name
        if not path.is_file() or root not in path.resolve().parents:
            raise ReleaseError('A source file resolves outside the source directory.')
        data = path.read_bytes()
        findings = inspect_content(name, data)
        if findings:
            raise ReleaseError(name + ': ' + ', '.join(findings))
        snapshot[name] = data
    if has_manifest:
        try:
            manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            raise ReleaseError('Invalid generated release manifest.') from None
        if manifest != make_manifest(snapshot):
            raise ReleaseError('Generated release manifest does not match the source files.')
    return snapshot


def check_index(root=ROOT):
    """When a Git index exists, also examine staged bytes, not just the worktree."""
    if not (Path(root) / '.git').exists():
        return
    rows = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root).decode('utf-8').split('\x00')
    for row in filter(None, rows):
        metadata, name = row.split('\t', 1)
        mode, sha, stage = metadata.split()
        if mode != '100644' or stage != '0' or name not in FILES:
            raise ReleaseError('Git index contains an unexpected path, mode or conflict.')
        data = subprocess.check_output(['git', 'cat-file', 'blob', sha], cwd=root)
        findings = inspect_content(name, data)
        if findings:
            raise ReleaseError('Git index content failed the release check: ' + name)


def build_archive(snapshot, destination):
    destination = Path(destination)
    if destination.suffix != '.zip':
        raise ReleaseError('Release archive must use a .zip extension.')
    if destination.exists():
        raise ReleaseError('Archive already exists; choose a new destination.')
    manifest = make_manifest(snapshot)
    content = dict(snapshot)
    content['RELEASE_MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo('quality-summary-demo/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    # Re-read every entry; verification does not trust the ZIP central directory alone.
    with zipfile.ZipFile(destination) as archive:
        expected = {'quality-summary-demo/' + name: data for name, data in content.items()}
        if set(archive.namelist()) != set(expected) or len(archive.infolist()) != len(expected):
            raise ReleaseError('Archive inventory verification failed.')
        for name, data in expected.items():
            if archive.read(name) != data:
                raise ReleaseError('Archive content verification failed.')
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'build'])
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'quality-summary-demo.zip')
    args = parser.parse_args(argv)
    try:
        snapshot = source_snapshot()
        check_index()
        if args.command == 'build':
            digest = build_archive(snapshot, args.output)
            print('Verified source archive SHA256: ' + digest)
        else:
            print(f'Release check passed: {len(snapshot)} explicitly allowed source files.')
        return 0
    except (ReleaseError, OSError, subprocess.CalledProcessError) as exc:
        # OS exception messages can expose user paths; keep them out of diagnostics.
        print(str(exc) if isinstance(exc, ReleaseError) else 'Cannot inspect or build the local release.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
