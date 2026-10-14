#!/usr/bin/env python3
"""Exercise fresh/legacy WHDLoad setup using the pinned archive in tmp/cache."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WHDLoadInstall(unittest.TestCase):
    def test_install_and_migration(self):
        archive = ROOT / 'tmp/cache/WHDLoad_20.1_dev.lzx'
        self.assertTrue(archive.is_file(), 'Download the pinned archive into tmp/cache first')
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory(
                    prefix='whdload-test-', dir=ROOT / 'tmp') as temporary:
                root = Path(temporary)
                prefix = root / 'prefix with spaces'
                share = prefix / 'share/amiga'
                if legacy:
                    for name in ('WHDLoad', 'WHDLoad-20.0'):
                        (share / name).mkdir(parents=True)
                        (share / name / 'old-marker').write_text(name)
                    (share / '.setup').mkdir()
                    (share / '.setup/WHDLoad-20.0').write_text('old stamp')
                env = dict(os.environ, PREFIX=str(prefix), AMIGA_SHARE=str(share),
                           BUILD=str(root / 'build'), CACHE=str(ROOT / 'tmp/cache'))
                command = ['/bin/bash', str(ROOT / 'scripts/setup.sh'), 'whdload']
                subprocess.run(command, env=env, check=True, capture_output=True)
                self.assertFalse(os.path.lexists(share / 'WHDLoad-20.0'))
                self.assertTrue((share / 'WHDLoad').is_dir())
                self.assertFalse((share / 'WHDLoad').is_symlink())
                self.assertFalse((share / 'WHDLoad/old-marker').exists())
                for line in (ROOT / 'manifest/whdload.tsv').read_text().splitlines():
                    if not line or line.startswith('#'):
                        continue
                    name, expected = line.split('\t')
                    self.assertEqual(hashlib.sha256((share / 'WHDLoad' / name).read_bytes()).hexdigest(), expected)
                if legacy:
                    self.assertFalse((share / '.replaced').exists())
                    self.assertFalse((share / '.setup/WHDLoad-20.0').exists())
                snapshot = {str(p.relative_to(share)): p.lstat().st_mtime_ns
                            for p in share.rglob('*')}
                subprocess.run(command, env=env, check=True, capture_output=True)
                self.assertEqual(snapshot, {str(p.relative_to(share)): p.lstat().st_mtime_ns
                                           for p in share.rglob('*')})


if __name__ == '__main__':
    unittest.main()
