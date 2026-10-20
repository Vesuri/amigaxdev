"""Native debugger input with bounded motion, an action log and owned-input cleanup.

Use while the CPU is stopped, inside ``with Input(g) as controls:``. Supply a
``log(record)`` callback to persist actions. Pointer coordinates and gameplay
assertions belong to the caller; this module never writes guest control state.
"""
from .gdbserve import require_harness


class Input:
    def __init__(self, g, log=None):
        require_harness(g, 'key', 'fields', 'mouse', 'input')
        self.g = g
        self.log = log or (lambda record: None)
        self.held = []
        self.actions = []

    def _send(self, command):
        reply = self.g.cmd('monitor ' + command, timeout=120)
        record = {'command': command, 'reply': reply}
        self.actions.append(record)
        self.log(record)
        if 'rror' in reply:
            raise RuntimeError(f'{command}: {reply}')
        return reply

    def _button(self, kind, name, pressed):
        if pressed not in (0, 1):
            raise ValueError('state must be 0 or 1')
        identity = (kind, name)
        # Remember before sending: an interrupted acknowledgement can still mean
        # the guest received the press, so cleanup must attempt its release.
        if pressed and identity not in self.held:
            self.held.append(identity)
        self._send(f'{kind} {name} {int(pressed)}')
        if not pressed and identity in self.held:
            self.held.remove(identity)

    def key(self, raw, pressed):
        if not isinstance(raw, int) or not 0 <= raw < 0x80:
            raise ValueError('raw key must be an integer in 0..127')
        self._button('key', f'{raw:02x}', pressed)

    def button(self, event, pressed):
        if not event.startswith(('JOY1_', 'JOY2_')) or not all(c.isalnum() or c == '_' for c in event):
            raise ValueError('expected a JOY1_ or JOY2_ input event')
        self._button('input', event, pressed)

    def fields(self, count):
        if not isinstance(count, int) or not 1 <= count <= 6000:
            raise ValueError('field count must be in 1..6000')
        self._send(f'fields {count}')

    def mouse(self, dx, dy, fields=2):
        if not all(isinstance(n, int) and -64 <= n <= 64 for n in (dx, dy)):
            raise ValueError('mouse deltas must be integers in -64..64')
        if not isinstance(fields, int) or not 1 <= fields <= 6000:
            raise ValueError('field count must be in 1..6000')
        self._send(f'mouse {dx} {dy}')
        self.fields(fields)

    def move_to(self, target, position, *, tolerance=1, max_steps=100, fields=2):
        """Read the game's pointer after each step; fail if it never reaches target."""
        if tolerance < 0 or max_steps < 1:
            raise ValueError('invalid pointer convergence bounds')
        for _ in range(max_steps):
            x, y = position()
            dx, dy = target[0] - x, target[1] - y
            if abs(dx) <= tolerance and abs(dy) <= tolerance:
                return x, y
            self.mouse(max(-64, min(64, dx)), max(-64, min(64, dy)), fields)
        x, y = position()
        if abs(target[0] - x) <= tolerance and abs(target[1] - y) <= tolerance:
            return x, y
        raise TimeoutError(f'pointer did not reach {target}; last position {(x, y)}')

    def release_all(self):
        errors = []
        for kind, name in list(reversed(self.held)):
            try: self._button(kind, name, False)
            except Exception as error: errors.append(error)
        if errors:
            raise RuntimeError('failed to release held input') from errors[0]

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        self.release_all()
