#!/usr/bin/env python3
"""Smoke test of the harness input commands on a native FS-UAE build:
    scripts/test_fsuae_input.py [FS-UAE]      (default $AMIGA_SHARE/fs-uae-arm/fs-uae)

Boots the Kickstart 1.3 ROM with no disk, headless and with JOY0=none (the harness default
that keeps the host mouse out), then checks what the emulated hardware reports: JOY0DAT for
`monitor mouse` and JOY1DAT for `monitor input` on the port-1 joystick. Mouse buttons and keys
are checked for acceptance only (the stub cannot read the CIAs), and bad arguments must be
refused. Reads no game bytes.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "share/pylib"))
from amigaxdev.gdbserve import Gdb, require_harness  # noqa: E402

LAUNCH = '''set -eu
. "$AMIGA_SHARE/env.sh"
. "$COMMON"
AMIGA_MODEL=A500 CHIP_KB=512 FAST_KB=0 SLOW_KB=0 KICKSTART="$KICK13"
DEBUG=1 WARP=1 DETERMINISTIC=1 JOY0=none WINDOW=none SOUND=0 AMIGA_MONITOR=
fsuae_claim_port >/dev/null
fsuae_launch
'''


def main(argv):
    share = os.environ.get("AMIGA_SHARE") or os.path.expanduser("~/.local/share/amiga")
    fsuae = argv[1] if len(argv) > 1 else os.path.join(share, "fs-uae-arm/fs-uae")
    (ROOT / "tmp").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="input-smoke-", dir=ROOT / "tmp"))
    env = dict(os.environ, AMIGA_SHARE=share, FSUAE=fsuae, COMMON=str(ROOT / "share/fsuae_common.sh"))
    out = subprocess.run(["/bin/bash", "-c", LAUNCH], cwd=work, env=env, capture_output=True,
                         text=True, check=True).stdout
    port = int(out.rsplit("port ", 1)[1].split(")")[0])
    g = None
    try:
        for _ in range(80):
            if subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                              capture_output=True).stdout:
                break
            time.sleep(0.25)
        g = Gdb(port, str(work), "@@INPUT-SMOKE@@")
        print("harness:", " ".join(sorted(require_harness(g, "key", "fields", "mouse", "input"))))
        check(g)
        print("input smoke test passed")
    finally:
        if g:
            try:
                g.cmd("kill", timeout=10)
            except Exception:
                pass
        # An emulator stopped in the stub ignores SIGTERM: this run's own pid gets SIGKILL.
        pid = work / ".run/fsuae.pid"
        if pid.exists():
            p = pid.read_text().split()[0]
            subprocess.run(["kill", p], capture_output=True)
            for _ in range(20):
                if subprocess.run(["kill", "-0", p], capture_output=True).returncode:
                    break
                time.sleep(0.25)
            else:
                subprocess.run(["kill", "-9", p], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


def check(g):
    def mon(text):
        return g.cmd("monitor " + text, timeout=120)

    def ok(text):
        r = mon(text)
        assert "rror" not in r, f"monitor {text}: {r}"

    def refused(text):
        assert "rror" in mon(text), f"monitor {text} was accepted"

    def word(addr):
        return int(re.findall(r":\s+0x([0-9a-f]+)", g.cmd(f"x/1hx {addr:#x}"))[0], 16)

    ok("fields 100")  # into the ROM's insert-disk loop
    # monitor mouse: JOY0DAT is Y counter (high byte), X counter (low byte), both mod 256.
    before = word(0xDFF00A)
    ok("mouse 10 -20")
    ok("fields 2")
    after = word(0xDFF00A)
    dx, dy = (after - before) & 0xFF, ((after >> 8) - (before >> 8)) & 0xFF
    assert (dx, dy) == (10, 256 - 20), f"JOY0DAT {before:04x} -> {after:04x}"
    # monitor input, port-1 joystick, decoded as games do: right is bit 1, left bit 9, down
    # bit 1 XOR bit 0, up bit 9 XOR bit 8 of JOY1DAT.
    def directions():
        v = word(0xDFF00C)
        return {d for d, on in (("RIGHT", v >> 1 & 1), ("LEFT", v >> 9 & 1),
                                ("DOWN", (v >> 1 ^ v) & 1), ("UP", (v >> 9 ^ v >> 8) & 1)) if on}
    for d in ("RIGHT", "LEFT", "DOWN", "UP"):
        assert directions() == set(), f"JOY1DAT {word(0xDFF00C):04x} before {d}"
        ok(f"input JOY2_{d} 1")
        ok("fields 2")
        assert directions() == {d}, f"JOY2_{d}: JOY1DAT {word(0xDFF00C):04x}"
        ok(f"input JOY2_{d} 0")
        ok("fields 2")
    # The stub cannot read the CIAs and keeps POTGOR as 0, so the mouse buttons (CIA-A PRA,
    # POTGOR) and keys (CIA-A SDR) are only checked for acceptance; game harnesses read the
    # result (Gunship's menu clicks, Prince of Persia's keys).
    for text in ("input JOY1_FIRE_BUTTON 1", "input JOY1_FIRE_BUTTON 0",
                 "input JOY1_2ND_BUTTON 1", "input JOY1_2ND_BUTTON 0", "key 40 1", "key 40 0"):
        ok(text)
        ok("fields 2")
    for bad in ("mouse 200 0", "mouse 1", "input SPC_QUIT 1", "input NO_SUCH_EVENT 1",
                "input JOY1_FIRE_BUTTON", "key 80 1"):
        refused(bad)


if __name__ == "__main__":
    main(sys.argv)
