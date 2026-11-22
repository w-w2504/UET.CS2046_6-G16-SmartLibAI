"""Guard against missing/tampered data and accidental cross-component reads."""

import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from p3_artifacts import MANIFEST, check_files, contained, verify_group, verify_package


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'search.bin').write_bytes(b'original')
        self.entry = {'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}
        manifest = {'schema_version': 2, 'groups': {
            'search_v4': {'files': {'search.bin': self.entry}},
            'reader_staging': {'files': {'missing-reader.bin': self.entry}}}}
        path = self.root / MANIFEST
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def test_search_does_not_require_reader(self):
        self.assertEqual(verify_group(self.root, 'search'), 1)

    def test_missing_required_data_fails(self):
        with self.assertRaises(FileNotFoundError):
            verify_group(self.root, 'reader')

    def test_same_size_tampering_fails(self):
        (self.root / 'search.bin').write_bytes(b'modified')
        with self.assertRaises(ValueError):
            verify_group(self.root, 'search')

    def test_size_tampering_fails(self):
        (self.root / 'search.bin').write_bytes(b'longer original')
        with self.assertRaises(ValueError):
            check_files(self.root, {'search.bin': self.entry})

    def test_outside_root_rejected(self):
        with self.assertRaises(ValueError):
            contained(self.root, '../outside.bin')

    def test_envelope_cannot_omit_required_data(self):
        (self.root / 'handoff_manifest.json').write_text(json.dumps({
            'component': 'search', 'files': {MANIFEST: self.entry}}), encoding='utf-8')
        with self.assertRaises(ValueError):
            verify_package(self.root, 'search')


if __name__ == '__main__':
    unittest.main()
