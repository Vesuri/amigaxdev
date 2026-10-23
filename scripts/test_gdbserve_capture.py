#!/usr/bin/env python3
"""A failed capture must never leave an image or trace behind, least of all an older one:
    scripts/test_gdbserve_capture.py [FS-UAE]      (default $AMIGA_SHARE/fs-uae-arm/fs-uae)

amigaxdev.gdbserve's `shot`, `profile` and Server.capture against a fake gdb: a disconnect, an
error reply, no trace, a partial trace, the wrong number of fields, a leftover temporary file
and a field without a screenshot must each raise CaptureError with a stale output file in place
and leave no output file. Then a real emulator (the A500 3.1 ROM with no disk, headless): a
successful `profile 2` and `shot` as controls, and after this run's emulator is killed, both
must fail the same way. Reads no game bytes.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "share/pylib"))
from amigaxdev import barto, gdbserve  # noqa: E402
from amigaxdev.gdbserve import CaptureError, Gdb, Server  # noqa: E402

LAUNCH = '''set -eu
. "$AMIGA_SHARE/env.sh"
. "$COMMON"
DEBUG=1 WARP=1 DETERMINISTIC=1 JOY0=none WINDOW=none SOUND=0 AMIGA_MONITOR=
fsuae_claim_port >/dev/null
fsuae_launch
'''


def trace_bytes(fields, shot=b"\x89PNG fake"):
    """A Barto trace with FIELDS empty fields, each with screenshot SHOT."""
    def u(*v):
        return struct.pack(f"<{len(v)}I", *v)
    def blob(b):
        return u(len(b)) + b
    out = u(fields, 0) + bytes(16) + blob(b"") + blob(b"") + blob(b"") + u(0, 0)
    for _ in range(fields):
        out += blob(b"") + blob(b"") + u(0, 0) + u(0, 0) + u(284204, 0, 0) + u(len(shot), 0) + shot
    return out


class FakeGdb:
    """gdb answering `monitor profile N "" "FILE"` by ACTION(n, file) -> reply text."""

    def __init__(self, action):
        self.action, self.running = action, False

    def cmd(self, text, timeout=30):
        assert text.startswith("monitor profile "), text
        n, _, path = text[len("monitor profile "):].partition(' "" ')
        return self.action(int(n), Path(path.strip('"')))

    def stop(self):
        pass

    def cont(self):
        pass


def write(data):
    def action(n, path):
        path.write_bytes(data(n))
        return ""
    return action


def disconnect(n, path):
    raise EOFError("Remote connection closed")


FAILURES = {
    "a disconnect": disconnect,
    "an error reply": lambda n, path: "Protocol error with Rcmd",
    "a dead connection": lambda n, path: "Remote connection closed",
    "no trace": lambda n, path: "",
    "a partial trace": write(lambda n: trace_bytes(n)[:-5]),
    "too few fields": write(lambda n: trace_bytes(n - 1)),
}


def expect_failure(what, call, outputs):
    for path in outputs:
        path.write_bytes(b"stale output of an earlier run")
    try:
        call()
    except CaptureError:
        pass
    else:
        raise AssertionError(f"{what}: the capture succeeded")
    left = [p.name for p in outputs if p.exists()]
    assert not left, f"{what}: {left} left behind"


def fake_checks(work):
    run = work / "run"
    run.mkdir()
    server = Server("capture-test", root=str(work), run_dir="run", profile_window=False)
    target, png = work / "trace.bin", work / "shot.png"
    partial = work / "trace.partial.bin"
    for name, action in FAILURES.items():
        g = FakeGdb(action)
        expect_failure(f"profile after {name}", lambda: gdbserve.profile(g, 2, target), [target])
        expect_failure(f"capture after {name}", lambda: server.capture(g, 2, str(target)), [target])
        expect_failure(f"shot after {name}", lambda: server.handle(g, f"shot {png}"), [png])
    # A temporary file left by an interrupted capture is not this capture's trace.
    partial.write_bytes(trace_bytes(2))
    expect_failure("profile with a leftover temporary file",
                   lambda: gdbserve.profile(FakeGdb(lambda n, path: ""), 2, target), [target])
    assert not partial.exists()
    expect_failure("shot of a field without a screenshot",
                   lambda: server.handle(FakeGdb(write(lambda n: trace_bytes(n, b""))), f"shot {png}"),
                   [png])
    # Controls: the same calls succeed on a complete trace.
    g = FakeGdb(write(trace_bytes))
    out, trace = gdbserve.profile(g, 2, target)
    assert len(barto.load(target).fields) == 2 and not partial.exists()
    reply = server.handle(g, f"shot {png}")
    assert png.read_bytes() == b"\x89PNG fake", reply
    assert server.handle(g, f"profile 3 {target}") == "ok" and len(barto.load(target).fields) == 3
    print(f"fake gdb: {len(FAILURES) + 2} failure kinds refused, stale outputs removed; controls pass")


def emulator_checks(fsuae, work):
    share = os.environ.get("AMIGA_SHARE") or os.path.expanduser("~/.local/share/amiga")
    env = dict(os.environ, AMIGA_SHARE=share, FSUAE=fsuae, COMMON=str(ROOT / "share/fsuae_common.sh"),
               FSUAE_RUN=".run", FSUAE_LOG=".run/fsuae.log", DEBUG_PORT="", AMIGA_SETUP="a500",
               EXTRA_ARGS="", NTSC="0", JOY1="none")
    out = subprocess.run(["/bin/bash", "-c", LAUNCH], cwd=work, env=env, capture_output=True,
                         text=True, check=True).stdout
    port = int(out.rsplit("port ", 1)[1].split(")")[0])
    pid = int((work / ".run/fsuae.pid").read_text().split()[0])
    comm = subprocess.run(["ps", "-o", "comm=", "-p", str(pid)], capture_output=True, text=True).stdout
    assert "fs-uae" in comm, f"pid {pid} is not this run's emulator: {comm!r}"
    g = None
    try:
        for _ in range(80):
            if subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                              capture_output=True).stdout:
                break
            time.sleep(0.25)
        g = Gdb(port, str(work), "@@CAPTURE-TEST@@")
        server = Server("capture-test", root=str(work), run_dir=".run", profile_window=False)
        target, png = work / "trace.bin", work / "shot.png"
        out, trace = gdbserve.profile(g, 2, target)
        assert len(trace.fields) == 2 and all(f.shot for f in trace.fields)
        server.handle(g, f"shot {png}")
        assert png.stat().st_size > 1000, png.stat().st_size
        print(f"emulator: profile 2 and shot pass ({png.stat().st_size} byte screenshot)")
        # This run's emulator dies; gdb stays.
        os.kill(pid, 9)
        for _ in range(40):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.25)
        expect_failure("profile after the emulator died", lambda: gdbserve.profile(g, 1, target), [target])
        expect_failure("shot after the emulator died", lambda: server.handle(g, f"shot {png}"), [png])
        print("emulator: profile and shot after a disconnect fail and leave no output")
    finally:
        if g:
            g.p.kill()
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass


def main(argv):
    share = os.environ.get("AMIGA_SHARE") or os.path.expanduser("~/.local/share/amiga")
    fsuae = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(share, "fs-uae-arm/fs-uae"))
    (ROOT / "tmp").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="capture-", dir=ROOT / "tmp"))
    try:
        (work / "fake").mkdir()
        fake_checks(work / "fake")
        (work / "emulator").mkdir()
        emulator_checks(fsuae, work / "emulator")
        print("capture test passed")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv)
