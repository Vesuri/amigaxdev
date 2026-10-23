"""Drive a game in FS-UAE through the Barto gdb stub: one server per project.

A project's tool (tools/td2.py and its kind) becomes a few lines:

    from amigaxdev.gdbserve import Server
    def frames(server, g, rest): ...          # a game command: return the reply text
    server = Server('td2', root=ROOT, commands={'frames': frames})
    if __name__ == '__main__':
        server.main(sys.argv[1:])

  python3 tools/td2.py serve          boot (amiga/run.sh DEBUG=1), attach gdb, run; listen
  python3 tools/td2.py <command...>   send one command to the running server, print the reply

Built-in commands (the emulator is left running after each unless noted):
  stop | cont                  halt / resume the CPU
  gdb <text>                   raw gdb CLI command (halts first, resumes after)
  shot <png>                   record one field, save its screenshot
  profile <fields> <bin>       cycle-exact trace of <fields> fields (Barto format)
  wait <seconds>               let it run
  until <addr>                 run to a breakpoint at addr and stay stopped there
  quit                         kill gdb and the emulator

`commands` entries take precedence over the built-ins, so a project can also replace one.
BOOT_BREAK=<addr> in the environment stops at addr before the server starts listening.

`shot`, `profile` and Server.capture go through profile(): a capture that fails (gdb error,
debugger disconnect, missing, partial or wrong-length trace) raises CaptureError and leaves
no output file, never an older one.
"""
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

from . import barto
from .env import tool

# This FS-UAE build's Barto stub (x86_64) leaves the profiler's PC window
# [baseText, baseText+sizeText) as [0x0100007f, +0) when no --remote_debugger_trigger is given
# (127.0.0.1 lands in baseText), so every trace record comes out without a PC.  Under WHDLoad no
# trigger can name the game, so set the window to everything through lldb before each capture.
# Addresses are this binary's link-time ones (baseText = 0x32dea04, read by start_cpu_profiler).
BASETEXT_VM = 0x32dea04


class _Reader:
    def read_until(self, token, timeout):
        end = time.time() + timeout
        while token.encode() not in self.buf:
            r, _, _ = select.select([self.p.stdout], [], [], max(0, end - time.time()))
            if not r:
                raise TimeoutError(self.buf.decode(errors='replace'))
            chunk = os.read(self.p.stdout.fileno(), 65536)
            if not chunk:
                raise EOFError(self.buf.decode(errors='replace'))
            self.buf += chunk
        i = self.buf.index(token.encode())
        out, self.buf = self.buf[:i], self.buf[i + len(token):]
        return out.decode(errors='replace')


class Gdb(_Reader):
    def __init__(self, port, run_dir, sentinel, gdb=None):
        env = dict(os.environ, HOME=os.path.join(run_dir, 'gdbhome'))
        os.makedirs(env['HOME'], exist_ok=True)
        self.sent = sentinel
        self.p = subprocess.Popen([gdb or tool('gdb'), '-q', '-nx'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                  bufsize=0)
        self.buf = b''
        self.running = False
        for c in ('set pagination off', 'set confirm off', 'set height 0', 'set width 0',
                  'set remotetimeout 120', 'set architecture m68k'):
            self.cmd(c)
        out = self.cmd(f'target remote 127.0.0.1:{port}', timeout=60)
        if 'Remote debugging' not in out and 'in ??' not in out and '0x' not in out:
            raise RuntimeError('connect failed:\n' + out)

    def cmd(self, text, timeout=30):
        # The pipe is unbuffered: a large script can be written in parts.
        payload = (text + f'\necho {self.sent}\\n\n').encode()
        while payload:
            written = self.p.stdin.write(payload)
            if not written:
                raise BrokenPipeError('gdb command pipe closed')
            payload = payload[written:]
        out = self.read_until(self.sent, timeout)
        return out.replace('(gdb) ', '').strip()

    def cont(self):
        if not self.running:
            self.p.stdin.write(b'continue &\n')
            time.sleep(0.2)
            self.running = True

    def stop(self):
        if self.running:
            self.p.stdin.write(b'interrupt\n')
            self.cmd('', timeout=30)
            time.sleep(0.3)
            self.running = False


class CaptureError(RuntimeError):
    """A `monitor profile` that did not produce the trace it asked for."""


# What gdb prints when a monitor command did not run: the stub's error reply, a dead or
# closed connection, no target.
GDB_FAILURES = ('Protocol error', 'Remote communication error', 'Remote connection closed',
                'The program is not being run', 'Cannot execute this command', 'Remote failure reply')


def profile(g, fields, target):
    """`monitor profile FIELDS` into TARGET: returns (gdb's reply, the barto.Trace). TARGET
    exists afterwards only if this capture wrote it whole: an older file is removed first, the
    stub writes a temporary file, and gdb's reply, the trace's parse and its field count are
    checked before that file takes TARGET's name. Raises CaptureError otherwise."""
    fields, target = int(fields), Path(target)
    partial = target.with_name(target.stem + '.partial' + target.suffix)
    for path in (target, partial):
        path.unlink(missing_ok=True)
    try:
        try:
            out = g.cmd(f'monitor profile {fields} "" "{partial}"', timeout=1800)
        except (TimeoutError, EOFError, OSError) as e:
            raise CaptureError(f'monitor profile {fields}: no reply from gdb '
                               f'({type(e).__name__}: {str(e)[-200:]})') from e
        failed = [m for m in GDB_FAILURES if m in out]
        if failed:
            raise CaptureError(f'monitor profile {fields} failed: {out[-300:]!r}')
        if not partial.exists():
            raise CaptureError(f'monitor profile {fields} wrote no trace (gdb said {out[-300:]!r})')
        try:
            trace = barto.load(partial)
        except Exception as e:
            raise CaptureError(f'monitor profile {fields} left an unreadable or partial trace '
                               f'({type(e).__name__}: {e})') from e
        if len(trace.fields) != fields:
            raise CaptureError(f'monitor profile {fields} traced {len(trace.fields)} fields')
        os.replace(partial, target)
        return out, trace
    finally:
        partial.unlink(missing_ok=True)


def require_harness(g, *commands):
    """The build's `monitor harness` capabilities (key, fields, mouse, input); raises with the
    fix when the build lacks the command or any of COMMANDS. A build without a harness command
    answers it with an error, which a caller that only reads replies would miss."""
    out = g.cmd('monitor harness', timeout=30)
    have = set() if 'rror' in out else set(out.split())
    missing = [c for c in commands if c not in have] if have else ['harness']
    if missing:
        raise RuntimeError(f'this FS-UAE lacks monitor {" ".join(missing)}; '
                           'rebuild the native builds with `make setup` in AmigaXDev '
                           f'(gdb said: {out!r})')
    return have


class Lldb(_Reader):
    """One lldb attached for the whole session: attaching to this x86_64 FS-UAE under Rosetta
    takes minutes, so it is done once, on the first capture, and the process kept running."""

    def __init__(self, run_dir, sentinel):
        self.sent = sentinel
        pid = open(os.path.join(run_dir, 'fsuae.pid')).read().strip()
        self.p = subprocess.Popen(['lldb', '-O', 'settings set target.preload-symbols false',
                                   '-p', pid], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, bufsize=0)
        self.buf = b''
        out = self.cmd('image list -o -f fs-uae', timeout=900)
        self.base = int(out.split('[  0] ')[1].split()[0], 16) + BASETEXT_VM
        self.cmd('script lldb.debugger.SetAsync(True)')  # else continue blocks the command loop
        self.cmd('process continue')

    def cmd(self, text, timeout=60):
        self.p.stdin.write((text + f"\nscript print('{self.sent}')\n").encode())
        return self.read_until(self.sent + '\n', timeout)


class Server:
    def __init__(self, name, root, run_script='amiga/run.sh', run_dir='amiga/.run', sock=None,
                 sentinel=None, commands=None, profile_window=True, gdb=None):
        """name: socket and sentinel stem; root: the project checkout.  profile_window: True to
        fix the stub's profiler window through lldb before each `profile` (the x86_64 build
        needs it), False to skip, or a callable(server) of the project's own."""
        self.name, self.root = name, root
        self.run_script = os.path.join(root, run_script)
        self.run_dir = os.path.join(root, run_dir)
        self.sock = sock or os.path.join(self.run_dir, f'{name}.sock')
        self.sent = sentinel or f'@@{name.upper()}-DONE@@'
        self.commands = dict(commands or {})
        self.profile_window = profile_window
        self.gdb_path = gdb
        self.lldb = None
        self.g = None

    # -- the stub's profiler window -----------------------------------------------------------

    def fix_profile_window(self):
        if self.lldb is None:
            self.lldb = Lldb(self.run_dir, self.sent)
        L, a = self.lldb, self.lldb.base
        L.cmd('process interrupt')
        while 'stopped' not in L.cmd('process status'):
            time.sleep(0.2)
        L.cmd(f'memory write -s4 {a:#x} 0')
        L.cmd(f'memory write -s4 {a + 4:#x} 0x7fffffff')
        out = L.cmd(f'memory read -s4 -fx -c2 {a:#x}')
        L.cmd('process continue')
        assert '0x00000000 0x7fffffff' in out, out

    # -- server ---------------------------------------------------------------------------------

    def boot(self, env=None):
        """Run the project's run script with DEBUG=1, attach gdb; returns the Gdb."""
        env = dict(os.environ, DEBUG='1', SILENT=os.environ.get('SILENT', '1'), **(env or {}))
        out = subprocess.run(['bash', self.run_script], env=env, capture_output=True, text=True,
                             check=True).stdout
        print(out, end='', flush=True)
        port = int(out.rsplit('port ', 1)[1].split(')')[0])
        for _ in range(80):
            if subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN'],
                              capture_output=True).stdout:
                break
            time.sleep(0.25)
        self.g = Gdb(port, self.run_dir, self.sent, self.gdb_path)
        print('attached; pc', self.g.cmd('info registers pc'), flush=True)
        return self.g

    def serve(self):
        g = self.boot()
        # Arm an address learned in a calibration boot before emulated time advances.
        # This prevents a fast warp boot from passing the first race during host polling.
        if os.environ.get('BOOT_BREAK'):
            g.cmd(f"break *{os.environ['BOOT_BREAK']}")
            if os.environ.get('BOOT_CONDITION'):
                g.cmd('condition $bpnum ' + os.environ['BOOT_CONDITION'])
            if os.environ.get('BOOT_IGNORE'):
                g.cmd('ignore $bpnum ' + os.environ['BOOT_IGNORE'])
            print(g.cmd('continue', timeout=1800), flush=True)
            g.cmd('delete')
        else:
            g.cont()
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        s = socket.socket(socket.AF_UNIX)
        s.bind(self.sock)
        s.listen(1)
        print('serving on', self.sock, flush=True)
        while True:
            c, _ = s.accept()
            line = self.read_request(c)
            try:
                reply = self.handle(g, line)
            except Exception as e:  # report and keep serving
                reply = f'ERROR {type(e).__name__}: {e}'
            try:
                c.sendall((reply + '\n').encode())
            except OSError:
                pass
            c.close()
            if line == 'quit':
                break

    @staticmethod
    def read_request(c):
        """One request: up to a newline or EOF. Clients that send neither (the projects' own
        socket helpers) are read until the data stops for a moment, so a request larger than
        one recv arrives whole."""
        data = c.recv(65536)
        try:
            c.settimeout(0.05)
            while data and not data.endswith(b'\n'):
                chunk = c.recv(65536)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        finally:
            c.settimeout(None)
        return data.decode().strip()

    def capture(self, g, fields, target):
        """`monitor profile` FIELDS fields into TARGET with the CPU halted; returns gdb's reply."""
        was = g.running
        g.stop()
        if self.profile_window is True:
            self.fix_profile_window()
        elif callable(self.profile_window):
            self.profile_window(self)
        try:
            out, _ = profile(g, fields, target)
        finally:
            if was:
                g.cont()
        return out

    def handle(self, g, line):
        op, _, rest = line.partition(' ')
        if op in self.commands:
            return self.commands[op](self, g, rest)
        if op == 'stop':
            g.stop()
            return g.cmd('info registers pc')
        if op == 'cont':
            g.cont()
            return 'running'
        if op == 'wait':
            g.cont()
            time.sleep(float(rest))
            return 'ok'
        if op == 'until':
            g.stop()
            g.cmd(f'break *{rest}')
            out = g.cmd('continue', timeout=1800)
            g.cmd('delete')
            return out
        if op == 'gdb':
            was = g.running
            g.stop()
            out = g.cmd(rest, timeout=600)
            if was:
                g.cont()
            return out
        if op == 'shot':
            target, png = os.path.join(self.run_dir, 'shot.bin'), Path(os.path.abspath(rest))
            png.unlink(missing_ok=True)
            was = g.running
            g.stop()
            try:
                out, trace = profile(g, 1, target)
            finally:
                if was:
                    g.cont()
            f = trace.fields[-1]
            if not f.shot:
                raise CaptureError('the traced field has no screenshot')
            partial = png.with_name(png.stem + '.partial' + png.suffix)
            partial.write_bytes(f.shot)
            os.replace(partial, png)
            return f'{png} kind={f.shot_kind} {len(f.shot)} bytes {out}'
        if op == 'profile':
            fields, target = rest.split(None, 1)
            return self.capture(g, fields, os.path.abspath(target)) or 'ok'
        if op == 'quit':
            g.p.kill()
            if self.lldb:
                self.lldb.p.kill()
            pid = open(os.path.join(self.run_dir, 'fsuae.pid')).read().strip()
            os.kill(int(pid), signal.SIGKILL)
            return 'bye'
        return 'unknown command'

    # -- client ---------------------------------------------------------------------------------

    def request(self, line):
        """Send one command to the running server; returns its reply."""
        c = socket.socket(socket.AF_UNIX)
        c.connect(self.sock)
        c.sendall(line.encode() + b'\n')
        out = b''
        while chunk := c.recv(65536):
            out += chunk
        return out.decode()

    def main(self, argv):
        if argv == ['serve']:
            self.serve()
        elif argv:
            print(self.request(' '.join(argv)), end='')
        else:
            sys.exit(__doc__)


def screenshot_from_trace(path):
    """(kind, bytes) of the last field's screenshot in a Barto profile file."""
    return barto.last_screenshot(path)
