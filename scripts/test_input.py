#!/usr/bin/env python3
"""Input ownership, failure cleanup, protocol errors and bounded pointer motion."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'share/pylib'))
from amigaxdev.input import Input


class Guest:
    def __init__(self):
        self.commands = []
        self.xy = [0, 0]
        self.fail = None
        self.stuck = False

    def cmd(self, command, **kwargs):
        self.commands.append(command)
        if command == 'monitor harness': return 'key fields mouse input'
        if command == self.fail: return 'Protocol error with Rcmd'
        if command.startswith('monitor mouse') and not self.stuck:
            dx, dy = map(int, command.split()[2:])
            self.xy[0] += dx
            self.xy[1] += dy
        return ''


class Inputs(unittest.TestCase):
    def test_cleanup_after_failure_and_release_order(self):
        g = Guest()
        with self.assertRaisesRegex(ValueError, 'game failed'):
            with Input(g) as c:
                c.key(0x40, True)
                c.button('JOY2_LEFT', True)
                c.button('JOY2_FIRE_BUTTON', True)
                c.button('JOY2_LEFT', False)
                raise ValueError('game failed')
        self.assertEqual(g.commands[-2:], ['monitor input JOY2_FIRE_BUTTON 0', 'monitor key 40 0'])
        self.assertEqual(c.held, [])

    def test_releases_other_inputs_after_protocol_error(self):
        g = Guest(); c = Input(g)
        c.key(0x40, True); c.button('JOY2_LEFT', True)
        g.fail = 'monitor input JOY2_LEFT 0'
        with self.assertRaises(RuntimeError): c.release_all()
        self.assertEqual(c.held, [('input', 'JOY2_LEFT')])
        self.assertEqual(g.commands[-1], 'monitor key 40 0')

    def test_pointer_feedback_and_timeout(self):
        g = Guest(); records = []; c = Input(g, records.append)
        self.assertEqual(c.move_to((150, -140), lambda: g.xy), (150, -140))
        self.assertEqual(len(records), 6)
        g.stuck = True
        with self.assertRaises(TimeoutError): c.move_to((0, 0), lambda: g.xy, max_steps=3)
        for record in records:
            if record['command'].startswith('mouse '):
                self.assertTrue(all(abs(int(n)) <= 64 for n in record['command'].split()[1:]))

    def test_validation_and_missing_capabilities(self):
        g = Guest(); c = Input(g)
        for operation in (lambda: c.key(128, True), lambda: c.button('SPC_QUIT', True),
                          lambda: c.fields(0), lambda: c.mouse(65, 0)):
            with self.assertRaises(ValueError): operation()
        self.assertEqual(g.commands, ['monitor harness'])
        g.fail = 'monitor mouse 1 1'
        with self.assertRaises(RuntimeError): c.mouse(1, 1)
        g.cmd = lambda *args, **kwargs: 'Protocol error with Rcmd'
        with self.assertRaisesRegex(RuntimeError, 'rebuild'): Input(g)


if __name__ == '__main__': unittest.main()
