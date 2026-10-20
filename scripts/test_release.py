#!/usr/bin/env python3
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'share/pylib'))
from amigaxdev import release


class Release(unittest.TestCase):
    def test_name_boundaries(self):
        for length in (29, 30):
            release.check_names(['a' * length, 'd/' + 'b' * length])
        for name in ('a' * 31, 'd/' + 'a' * 31, 'Prince of Persia 2 Install.info',
                     '../file', '/file', 'a//b', 'a\\b', 'DH0:file', 'bad\nname'):
            with self.subTest(name=name), self.assertRaises(ValueError): release.check_names([name])
        release.check_names(['PoP2 Install.info', 'PoP2 Install/Install.info'])
        release.check_names(['d' * 25 + '.info'])
        with self.assertRaises(ValueError): release.check_names(['d' * 26 + '.info'])
        with self.assertRaises(ValueError): release.check_names(['Game', 'game'])
        with self.assertRaises(UnicodeEncodeError): release.check_names(['caf\u00e9'])
        release.check_names(['x' * 31], component_limit=107)

    def test_extracted_icon_pairing(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temp:
            root = Path(temp); (root / 'Game').mkdir()
            expected = ['Game.info', 'Game/Install', 'Game/Install.info']
            for name in expected: (root / name).write_bytes(b'authored fixture')
            release.check_extracted_names(root, expected)
            (root / 'Game/Install.info').rename(root / 'Game/Install.inf')
            with self.assertRaises(ValueError): release.check_extracted_names(root, expected)

    def test_archive_rejects_before_compression(self):
        with patch.object(release, 'member') as member:
            with self.assertRaises(ValueError): release.archive('x' * 26, {}, b'', 0)
            member.assert_not_called()

    def test_audited_executable_and_build_modes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temp:
            exe = Path(temp) / 'Game'; exe.write_bytes(b'\0\0\x03\xf3authored')
            data = exe.read_bytes()
            policy = dict(diagnostic_patterns=['runtime_sha', 'trace_counter'], runtime_symbols=['reject_bad_extent'])
            base = '00000001 g F .text 00000010 reject_bad_extent\n'
            diag = '00000002 g F .text 00000010 runtime_sha\n00000003 g O .bss 00000004 trace_counter\n'
            for verify, symbols in ((False, base), (True, base + diag)):
                with patch.object(release.subprocess, 'check_output', return_value=symbols):
                    release.audit_executable('Game.elf', exe, lambda elf: data, verification=verify, **policy)
                    with self.assertRaises(ValueError):
                        release.audit_executable('Game.elf', exe, lambda elf: data, verification=not verify, **policy)
            with patch.object(release.subprocess, 'check_output', return_value=base):
                exe.write_bytes(data + b'stale')
                with self.assertRaisesRegex(ValueError, 'differs'):
                    release.audit_executable('Game.elf', exe, lambda elf: data, **policy)
            with patch.object(release.subprocess, 'check_output', return_value=diag):
                with self.assertRaisesRegex(ValueError, 'runtime guards'):
                    release.audit_executable('Game.elf', exe, lambda elf: data, verification=True, **policy)


if __name__ == '__main__': unittest.main()
