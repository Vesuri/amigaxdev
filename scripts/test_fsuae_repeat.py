#!/usr/bin/env python3
"""Repeatability test of the gdb stub's stops and harness commands on a native FS-UAE build:
    scripts/test_fsuae_repeat.py [FS-UAE] [SETUP...]   (default $AMIGA_SHARE/fs-uae-arm/fs-uae;
                                                        setups a1200-fast and a500)

Boots the setup's 3.1 Kickstart with no disk (WARP=1 DETERMINISTIC=1 JOY0=none, no window, no
sound) and drives the stub over the gdb remote protocol, without gdb. One sequence: `fields`
from the reset stop; a breakpoint on the level-2 interrupt handler (a mid-field stop) and
`fields` from it; `fields` from a field boundary; chained `profile` chunks; a register read
between chunks; a Ctrl-C. It runs twice in fresh emulators, which must agree on registers, beam
position, chip RAM and the guest's field counter at every stop and on every trace (per-field
cycles, instructions with registers, DMA records, custom registers, chip RAM, screenshot). A
Ctrl-C lands at a vsync chosen by host timing, so after it only checks within one run apply.
On a build that reports `exact-fields gapless-profile`: every command must advance the guest's
own field counter (GfxBase->VBCounter) by the fields it should run, every stop at a vsync must
read the same beam position, and a third emulator, with `fields 2` split in two, profiles the
chained chunks' fields in one `profile`; each field must match. Reads no game bytes.
"""
import concurrent.futures
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "share/pylib"))
from amigaxdev import barto  # noqa: E402

LAUNCH = '''set -eu
. "$AMIGA_SHARE/env.sh"
. "$COMMON"
DEBUG=1 WARP=1 DETERMINISTIC=1 JOY0=none WINDOW=none SOUND=0 AMIGA_MONITOR=
fsuae_claim_port >/dev/null
fsuae_launch
'''
CHIP = {"a1200-fast": 0x200000, "a500": 0x80000}


class Stub:
    """One fresh emulator and a raw gdb remote protocol connection to its stub."""

    def __init__(self, fsuae, setup):
        share = os.environ.get("AMIGA_SHARE") or os.path.expanduser("~/.local/share/amiga")
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="repeat-", dir=ROOT / "tmp"))
        env = dict(os.environ, AMIGA_SHARE=share, FSUAE=fsuae, AMIGA_SETUP=setup,
                   COMMON=str(ROOT / "share/fsuae_common.sh"), FSUAE_RUN=".run",
                   FSUAE_LOG=".run/fsuae.log", DEBUG_PORT="", EXTRA_ARGS="", NTSC="0", JOY1="none")
        out = subprocess.run(["/bin/bash", "-c", LAUNCH], cwd=self.work, env=env, capture_output=True,
                             text=True, check=True).stdout
        port = int(out.rsplit("port ", 1)[1].split(")")[0])
        for _ in range(80):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                time.sleep(0.25)
        else:
            self.close()
            raise RuntimeError(f"no gdb stub on port {port}")
        self.s.settimeout(900)
        self.buf = b""

    def reply(self):
        """The next packet's body; console output packets are skipped."""
        while True:
            while b"#" not in self.buf or len(self.buf) < self.buf.index(b"#") + 3:
                data = self.s.recv(65536)
                if not data:
                    raise EOFError("stub closed the connection")
                self.buf += data
            i = self.buf.index(b"$")
            j = self.buf.index(b"#", i)
            body, self.buf = self.buf[i + 1:j].decode(), self.buf[j + 3:]
            self.s.sendall(b"+")
            if not (body.startswith("O") and body != "OK"):
                return body

    def send(self, body, wait=True):
        self.s.sendall(b"$%s#%02x" % (body.encode(), sum(body.encode()) & 0xFF))
        return self.reply() if wait else None

    def mon(self, text):
        r = self.send("qRcmd," + text.encode().hex())
        assert r == "OK" or not r.startswith("E"), f"monitor {text}: {r}"
        return r if r in ("OK", "") else bytes.fromhex(r).decode()

    def mem(self, addr, n):
        out = b""
        while n:
            k = min(n, 240)
            out += bytes.fromhex(self.send(f"m{addr:x},{k:x}"))
            addr, n = addr + k, n - k
        return out

    def beam(self):
        v = self.mem(0xDFF004, 4)
        return ((v[1] & 7) << 8) | v[2], v[3]

    def cont_until_stop(self):
        self.send("vCont;c", wait=False)
        return self.reply()

    def interrupt_after(self, seconds):
        self.send("vCont;c", wait=False)
        time.sleep(seconds)
        self.s.sendall(b"\x03")
        return self.reply()

    def close(self):
        try:
            self.send("k", wait=False)
        except (OSError, AttributeError):
            pass
        # An emulator stopped in the stub ignores SIGTERM: this run's own pid gets SIGKILL.
        pid = self.work / ".run/fsuae.pid"
        if pid.exists():
            p = pid.read_text().split()[0]
            subprocess.run(["kill", p], capture_output=True)
            for _ in range(20):
                if subprocess.run(["kill", "-0", p], capture_output=True).returncode:
                    break
                time.sleep(0.25)
            else:
                subprocess.run(["kill", "-9", p], capture_output=True)
        shutil.rmtree(self.work, ignore_errors=True)


def digest(data):
    return hashlib.sha256(data).hexdigest()[:16]


def fields_of(path):
    """Per field: (cycles, signature without the screenshot, screenshot digest) and the
    chunk's chip RAM digest."""
    t = barto.load(path)
    out = []
    for f in t.fields:
        sig = digest(bytes(f.custom) + bytes(f.aga_colors) + bytes(f.dma)
                     + f.idle.to_bytes(4, "little") + bytes(t.data[f.insn_off:f.insn_end]))
        out.append((f.cycles, sig, digest(f.shot)))
    return out, digest(t.chip)


class Run:
    def __init__(self, stub, chip):
        self.e, self.chip, self.steps, self.n, self.vbcounter = stub, chip, [], 0, None

    def snap(self, step, reply, expect=None, regs=False, chip=False):
        """Beam, field counter and memory first: they are read where the stub stopped, even
        when parked at a vsync; a register read then moves a parked stop to the next
        instruction. expect: the fields the step should have run."""
        rec = {"step": step, "reply": reply, "expect": expect, "beam": self.e.beam()}
        if self.vbcounter:
            rec["vbcounter"] = int.from_bytes(self.e.mem(self.vbcounter, 4), "big")
        if chip:
            rec["chip"] = digest(self.e.mem(0, self.chip))
        if regs:
            rec["regs"] = self.e.send("g")
            rec["beam at regs"] = self.e.beam()
        self.steps.append(rec)
        return rec

    def profile(self, n, step, expect=None):
        path = self.e.work / f"p{self.n}.bin"
        self.n += 1
        rec = self.snap(step, self.e.mon(f'profile {n} "" "{path}"'), n if expect is None else expect)
        rec["fields"], rec["chunk chip"] = fields_of(path)
        path.unlink()
        return rec["fields"]

    def find_vbcounter(self):
        """GfxBase->VBCounter (graphics.library V39+): the guest's own count of vertical
        blanks, read from memory, so it counts fields independently of the stub."""
        e = self.e
        def long(a):
            return int.from_bytes(e.mem(a, 4), "big")
        node = long(long(4) + 0x17A)                        # ExecBase->LibList
        while long(node):
            if e.mem(long(node + 10), 17) == b"graphics.library\0":
                self.vbcounter = node + 500
                return
            node = long(node)
        raise RuntimeError("graphics.library not found")


def level2_handler(e):
    return int.from_bytes(e.mem(0x68, 4), "big")


def prefix(run, split):
    """Boot, a breakpoint (a mid-field stop) and fields from it, then fields from a field
    boundary: in one command, or split in two (split). Field numbers in comments count from
    the field F0 that holds the breakpoint stop."""
    e = run.e
    run.harness = e.mon("harness").split()
    reply = e.mon("fields 300")
    run.find_vbcounter()
    run.snap("fields 300 from the reset stop", reply, regs=True, chip=True)
    l2 = level2_handler(e)
    assert e.send(f"Z0,{l2:x},2") == "OK"
    reply = e.cont_until_stop()
    assert e.send(f"z0,{l2:x},2") == "OK"
    run.snap("breakpoint on the level-2 handler", reply, regs=True, chip=True)
    run.snap("fields 1 from the breakpoint", e.mon("fields 1"), 1)         # to F0+2
    run.profile(1, "profile 1")                                            # F0+2
    if split:
        run.snap("fields 1 from a field boundary", e.mon("fields 1"), 1)
        run.snap("fields 1 from a field boundary", e.mon("fields 1"), 1)   # to F0+5
    else:
        run.snap("fields 2 from a field boundary", e.mon("fields 2"), 2)   # to F0+5


def sequence(fsuae, setup):
    """The repeated sequence."""
    e = Stub(fsuae, setup)
    try:
        run = Run(e, CHIP[setup])
        prefix(run, split=False)
        run.chained = len(run.steps)
        run.profile(2, "profile 2, chained")                                   # F0+5, F0+6
        run.profile(2, "profile 2, chained")                                   # F0+7, F0+8
        run.profile(1, "profile 1, chained")                                   # F0+9
        run.snap("registers between chunks", "", 0, regs=True, chip=True)
        # A register read moves the stop off the vsync, so the next profile starts at the
        # following one: one field runs untraced.
        run.profile(1, "profile 1 after a register read", 2)                   # F0+11
        run.snap("registers", "", 0, regs=True)
        run.snap("fields 1 after a register read", e.mon("fields 1"), 1)       # to F0+13
        run.profile(1, "profile 1")                                            # F0+13
        run.ctrl_c = len(run.steps)
        run.snap("Ctrl-C", e.interrupt_after(0.5))
        run.profile(1, "profile 1 after Ctrl-C")
        run.snap("registers after Ctrl-C", "", 0, regs=True)
        run.snap("fields 2 after Ctrl-C", e.mon("fields 2"), 2)
        run.profile(1, "profile 1")
        return run
    finally:
        e.close()


def reference(fsuae, setup):
    """The chained chunks' fields from one profile, after fields 2 split in two."""
    e = Stub(fsuae, setup)
    try:
        run = Run(e, CHIP[setup])
        prefix(run, split=True)
        return run, run.profile(5, "profile 5")                                # F0+5 .. F0+9
    finally:
        e.close()


def check(runs, ref):
    a, b = runs
    failures = []
    # Before the Ctrl-C both runs must agree on everything.
    for x, y in zip(a.steps[:a.ctrl_c], b.steps[:b.ctrl_c]):
        for k in x:
            if x[k] != y[k]:
                failures.append(f"{x['step']}: {k} differs between runs: {x[k]!r} vs {y[k]!r}")
    cycles = {f[0] for run in runs for s in run.steps for f in s.get("fields", [])}
    if len(cycles) != 1:
        failures.append(f"fields of different lengths: {sorted(cycles)}")
    if ref is None:
        return failures
    ref_run, ref_fields = ref
    for run in (a, b, ref_run):
        for prev, s in zip(run.steps, run.steps[1:]):
            ran = s["vbcounter"] - prev["vbcounter"]
            if s["expect"] is not None and ran != s["expect"]:
                failures.append(f"{s['step']}: ran {ran} fields, expected {s['expect']}")
    chained = [f for s in a.steps[a.chained:a.chained + 3] for f in s["fields"]]
    for i, (x, y) in enumerate(zip(chained, ref_fields)):
        if x[:2] != y[:2]:
            failures.append(f"chained field F0+{5 + i} differs from the same field in one profile")
    parked = {tuple(s["beam"]) for run in (a, b, ref_run) for s in run.steps
              if s["step"].startswith(("fields ", "profile ", "Ctrl-C"))}
    if len(parked) != 1:
        failures.append(f"stops at a vsync read different beam positions: {sorted(parked)}")
    return failures


def main(argv):
    share = os.environ.get("AMIGA_SHARE") or os.path.expanduser("~/.local/share/amiga")
    fsuae = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(share, "fs-uae-arm/fs-uae"))
    setups = argv[2:] or ["a1200-fast", "a500"]
    failed = False
    for setup in setups:
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            jobs = [pool.submit(sequence, fsuae, setup) for _ in range(2)]
            ref_job = pool.submit(reference, fsuae, setup)
            runs = [j.result() for j in jobs]
            exact = {"exact-fields", "gapless-profile"} <= set(runs[0].harness)
            ref = ref_job.result() if exact else None
        failures = check(runs, ref)
        length = {f[0] for s in runs[0].steps for f in s.get("fields", [])}
        ran = [f"{s['step'].split(',')[0]}: {s['vbcounter'] - p['vbcounter']}"
               for p, s in zip(runs[0].steps, runs[0].steps[1:]) if s["expect"] is not None]
        print(f"{setup}: {len(runs[0].steps)} steps, field length {sorted(length)} cycles, "
              f"{'exact fields and gapless profiles checked' if exact else 'build without exact-fields: repeatability only'}")
        print("  fields run:", "; ".join(ran))
        for f in failures:
            print("  FAIL", f)
        failed |= bool(failures)
    if failed:
        sys.exit(1)
    print("repeatability test passed")


if __name__ == "__main__":
    main(sys.argv)
