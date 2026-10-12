#!/usr/bin/env python3
"""Check launcher arguments without starting an emulator or reading game/ROM bytes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "share/fsuae_common.sh"


class Setups(unittest.TestCase):
    def setUp(self):
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="setup-test-", dir=ROOT / "tmp")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.stub = self.work / "fake emulator"
        self.stub.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
        self.stub.chmod(0o755)

    def run_launcher(self, setup="", mode="exec", extra="", common=COMMON, before=""):
        env = {key: os.environ[key] for key in ("HOME", "PATH")}
        env.update(COMMON=str(common), FSUAE=str(self.stub), AMIGA_SETUP=setup,
                   AMIGA_SHARE=str(self.work / "shared files"), EXTRA_ARGS=extra)
        script = '''set -eu
. "$COMMON"
AMIGA_MODEL=A4000 CPU=68040-NOMMU CHIP_KB=8192 FAST_KB=2048 SLOW_KB=1024
KICKSTART="wrong ROM"
fsuae_options || exit 1
''' + before + '\n'
        args = (' --amiga_model=A4000 --cpu=68040-NOMMU --chip_memory=8192'
                ' --uae_mmu_model=0 --uae_fpu_model=0 --jit_compiler=1'
                ' --uae_cpu_frequency=1 --uae_cpu_speed=max --uae_chipset=aga'
                ' --kickstart_file=wrong --hard_drive_0="game drive"')
        if mode == "exec":
            script += 'fsuae_exec' + args
        else:
            script += 'fsuae_launch' + args + ' >/dev/null\nwait "$FSUAE_PID"\ncat "$FSUAE_RUN/fsuae.log"'
        return subprocess.run(["/bin/bash", "-c", script], cwd=self.work, env=env,
                              text=True, capture_output=True)

    def effective(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        values = {}
        for line in result.stdout.splitlines():
            key, sep, value = line.partition("=")
            self.assertTrue(sep, line)
            values.setdefault(key.removeprefix("--"), value)
        return values

    def test_presets_both_launch_paths(self):
        cases = [
            ("a500", "A500", "68000", 512, 0, 512, 0, 0, 7093790),
            ("a500+", "A500+", "68000", 1024, 0, 0, 0, 0, 7093790),
            ("a1200", "A1200", "68EC020", 2048, 0, 0, 0, 0, 14187580),
            ("a1200-fast", "A1200", "68EC020", 2048, 8192, 0, 0, 0, 14187580),
            ("a1200-030", "A1200", "68030", 2048, 8192, 0, 68030, 0, 50000000),
            ("a1200-040", "A1200", "68040", 2048, 8192, 0, 68040, 68040, 25000000),
            ("a1200-060", "A1200", "68060", 2048, 8192, 0, 68060, 68060, 50000000),
        ]
        keys = ("amiga_model", "cpu", "chip_memory", "fast_memory", "slow_memory",
                "uae_mmu_model", "uae_fpu_model", "uae_cpu_frequency")
        for case in cases:
            for mode in ("exec", "launch"):
                with self.subTest(setup=case[0], mode=mode):
                    values = self.effective(self.run_launcher(case[0], mode))
                    self.assertEqual([values[k] for k in keys], list(map(str, case[1:])))
                    self.assertEqual(values["hard_drive_0"], "game drive")
                    self.assertEqual(values["jit_compiler"], "0")
                    rom = "kick40063.A600" if case[0].startswith("a500") else "kick40068.A1200"
                    self.assertEqual(values["kickstart_file"], str(self.work / "shared files/Kickstarts" / rom))

    def test_extra_args_override_preset(self):
        values = self.effective(self.run_launcher("a1200-fast", extra="--fast_memory=4096"))
        self.assertEqual(values["fast_memory"], "4096")

    def test_reapply_after_project_changes(self):
        values = self.effective(self.run_launcher("a1200-060", before="CPU=68000 FAST_KB=0"))
        self.assertEqual(values["cpu"], "68060")
        self.assertEqual(values["fast_memory"], "8192")

    def test_ntsc_clock(self):
        values = self.effective(self.run_launcher("a1200", before="NTSC=1\nfsuae_options"))
        self.assertEqual(values["uae_cpu_frequency"], "14318180")
        self.assertEqual(values["ntsc_mode"], "1")

    def test_exports_and_cached_options(self):
        before = '''/bin/bash -c 'test "$AMIGA_MODEL/$CPU/$CHIP_KB/$FAST_KB/$SLOW_KB" = A1200/68040/2048/8192/0' || exit 2
AMIGA_SETUP=typo
'''
        result = self.run_launcher("a1200-040", before=before)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown AMIGA_SETUP", result.stderr)
        self.assertFalse((self.work / ".run/fsuae.pid").exists())

    def test_bad_name_never_launches(self):
        result = self.run_launcher("typo")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown AMIGA_SETUP", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.work / ".run/fsuae.pid").exists())

    def test_no_preset_keeps_legacy_precedence(self):
        values = self.effective(self.run_launcher())
        self.assertEqual(values["amiga_model"], "A4000")
        self.assertEqual(values["uae_mmu_model"], "0")
        self.assertEqual(values["kickstart_file"], "wrong")


if __name__ == "__main__":
    unittest.main()
