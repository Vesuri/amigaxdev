#!/usr/bin/env python3
"""Check effective native-emulator settings, not option acknowledgements.

Uses installed ROMs, no game data. Scratch output stays under tmp/. Pass a native
FS-UAE path optionally; no JIT timing or hardware performance claims are made.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def stop(pid, p):
    """SIGTERM, then SIGKILL after 1 s. With fsuae_exec the emulator is p itself, which
    stays a zombie until p.poll() reaps it."""
    def gone():
        if pid == p.pid:
            return p.poll() is not None
        try: os.kill(pid, 0)
        except ProcessLookupError: return True
        return False
    for sig in (15, 9):
        try: os.kill(pid, sig)
        except ProcessLookupError: return
        for _ in range(4):
            if gone(): return
            time.sleep(.25)


def run(binary, setup, extra, mode, common=None):
    with tempfile.TemporaryDirectory(prefix='config-smoke-', dir=ROOT / 'tmp') as temp:
        work = Path(temp)
        env = dict(os.environ, COMMON=str(common or ROOT / 'share/fsuae_common.sh'),
                   FSUAE=str(binary), AMIGA_SETUP=setup, EXTRA_ARGS=extra, AMIGA_MONITOR='',
                   FSUAE_RUN='.run', FSUAE_LOG='.run/fsuae.log', DEBUG='0', NTSC='0')
        script = '''set -eu
. "$COMMON"
WINDOW=none SOUND=0 WARP=1
'''
        script += ('fsuae_exec' if mode == 'exec' else 'fsuae_launch\nwait "$FSUAE_PID"')
        with (work / 'stdout').open('w') as output:
            p = subprocess.Popen(['/bin/bash', '-c', script], cwd=work, env=env,
                                 stdout=output, stderr=subprocess.STDOUT)
            try:
                log = work / '.run/fsuae/Cache/Logs/fs-uae.log.txt'
                config = log.with_name('debug.uae')
                for _ in range(150):
                    text = log.read_text(errors='replace') if log.exists() else ''
                    reports = re.findall(r'CPU=(\d+), FPU=(\d+).*?MMU=(\d+), JIT=(\d+)', text)
                    if reports and config.exists():
                        values = dict(line.split('=', 1) for line in config.read_text().splitlines()
                                      if '=' in line and not line.startswith(';'))
                        return values, tuple(map(int, reports[-1]))
                    if p.poll() is not None:
                        launch_log = work / '.run/fsuae.log'
                        raise RuntimeError((work / 'stdout').read_text() +
                                           (launch_log.read_text() if launch_log.exists() else ''))
                    time.sleep(.2)
                raise TimeoutError('No effective CPU report: ' + (work / 'stdout').read_text())
            finally:
                # Kill only this launch. The background launcher records its own child. A
                # headless emulator ignores SIGTERM, so it gets SIGKILL after 1 s.
                pidfile = work / '.run/fsuae.pid'
                if pidfile.exists():
                    pid = int(pidfile.read_text().split()[0])
                    stop(pid, p)
                p.terminate()
                try: p.wait(timeout=3)
                except subprocess.TimeoutExpired: p.kill(); p.wait()


def main():
    share = Path(os.environ.get('AMIGA_SHARE', Path.home() / '.local/share/amiga'))
    binary = Path(sys.argv[1]) if len(sys.argv) > 1 else share / 'fs-uae-arm/fs-uae'
    (ROOT / 'tmp').mkdir(exist_ok=True)
    cases = [
        ('a3000', '', (68030, 68882, 68030, 0), {'z3mem_size': '0', 'cpu_frequency': '25000000', 'cpu_data_cache': 'true'}),
        ('a3000', '--zorro_iii_memory=32768 --uae_z3mem_size=16', (68030, 68882, 68030, 0), {'z3mem_size': '32', 'cpu_frequency': '25000000', 'cpu_data_cache': 'true'}),
        ('a1200-040', '', (68040, 68040, 68040, 0), {'z3mem_size': '0', 'cpu_data_cache': 'true'}),
        ('a1200-040', '--cpu=68040-NOMMU --uae_z3mem_size=32 --uae_cpu_data_cache=false', (68040, 68040, 0, 0), {'z3mem_size': '32', 'cpu_data_cache': 'false'}),
    ]
    for mode in ('exec', 'launch'):
        for setup, extra, cpu, expected in cases:
            values, report = run(binary, setup, extra, mode)
            assert report == cpu, (mode, setup, extra, report, cpu)
            for key, value in expected.items():
                assert values.get(key) == value, (mode, setup, key, values.get(key), value)
            assert values['chipmem_size'] == '4'
            assert values['fastmem_size'] == '8'
            assert values['cachesize'] == '0'
            print('PASS', mode, setup, extra or 'defaults')
    # Native builds cannot provide JIT. The launcher must say so rather than
    # treating a zero-sized translation cache as successful enablement.
    for mode in ('exec', 'launch'):
        try: run(binary, 'a1200-040', '--jit_compiler=1', mode)
        except RuntimeError as error:
            assert 'JIT disabled' in str(error), str(error)
        else: raise AssertionError('JIT request silently accepted by native build')
    print('effective configuration checks passed (native JIT unavailable)')


if __name__ == '__main__':
    main()
