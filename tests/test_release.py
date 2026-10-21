import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

path = Path(__file__).resolve().parents[1] / 'tools' / 'release.py'
spec = importlib.util.spec_from_file_location('release', path)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_example_has_expected_digest(self):
        path = release.ROOT / 'examples' / 'synthetic.csv'
        self.assertEqual(release.inspect_content('examples/synthetic.csv', path.read_bytes()), [])
        self.assertIn('bundled synthetic data changed', release.inspect_content('examples/synthetic.csv', b'changed data'))

    def test_flags_credentials_without_printing_values(self):
        sample = ('password' + " = '" + 'synthetic_value' + "'").encode()
        self.assertIn('literal credential', release.inspect_content('README.md', sample))

    def test_app_cannot_import_network_or_process_modules(self):
        for module in ['socket', 'urllib.request', 'subprocess', 'os']:
            with self.subTest(module=module):
                self.assertIn('application import outside offline allowlist', release.inspect_content('quality_summary/core.py', ('import ' + module).encode()))

    def test_app_cannot_execute_dynamic_code(self):
        self.assertIn('dynamic code execution', release.inspect_content('quality_summary/core.py', b"eval('1+1')"))

    def test_inventory_rejects_missing_and_unknown_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'unexpected.txt').write_text('synthetic extra')
            with self.assertRaises(release.ReleaseError):
                release.source_snapshot(root)

    def test_bundle_is_deterministic_and_manifest_matches_payload(self):
        snapshot = {'README.md': b'synthetic readme\n', 'examples/synthetic.csv': b'demo\n'}
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'first.zip', Path(directory) / 'second.zip'
            self.assertEqual(release.build_archive(snapshot, first), release.build_archive(snapshot, second))
            with zipfile.ZipFile(first) as archive:
                manifest = json.loads(archive.read('quality-summary-demo/RELEASE_MANIFEST.json'))
                self.assertEqual({entry['path'] for entry in manifest['files']}, set(snapshot))
                self.assertEqual(len(archive.infolist()), len(snapshot) + 1)
                self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))

    def test_existing_archive_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'source.zip'
            archive.write_bytes(b'existing synthetic file')
            with self.assertRaises(release.ReleaseError):
                release.build_archive({'README.md': b'demo'}, archive)
            self.assertEqual(archive.read_bytes(), b'existing synthetic file')

    def test_extracted_source_can_be_checked_and_manifest_cannot_be_tampered(self):
        snapshot = release.source_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'source.zip'
            release.build_archive(snapshot, archive)
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(root / 'unpacked')
            unpacked = root / 'unpacked' / 'quality-summary-demo'
            self.assertEqual(release.source_snapshot(unpacked), snapshot)
            (unpacked / 'RELEASE_MANIFEST.json').write_text('{}')
            with self.assertRaises(release.ReleaseError):
                release.source_snapshot(unpacked)


if __name__ == '__main__':
    unittest.main()
