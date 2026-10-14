#!/usr/bin/env python3
"""amigaxdev.callprofile on a synthetic Barto trace: python3 scripts/test_callprofile.py"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'share', 'pylib'))
from amigaxdev.callprofile import Reduction  # noqa: E402

GAP = 0x7fffffff


def blob(b):
    return struct.pack('<I', len(b)) + b


def trace(fields, chip):
    """fields: lists of (pc or None or GAP, cycles, sp); dma bytes are one free + one CPU slot."""
    out = struct.pack('<II', len(fields), 0) + bytes(16) + blob(b'') + blob(chip) + blob(b'')
    out += struct.pack('<II', 0, 0)
    for recs in fields:
        words = []
        for pc, cost, sp in recs:
            if pc is not None:
                words.append(pc)
            words.append(0xffffffff - cost)
            regs = [0] * 17
            regs[15] = sp
            words.extend(regs)
        dma = bytes(29) + b'\x00' + bytes(2) + bytes(29) + b'\x02' + bytes(2)
        out += blob(b'') + blob(b'') + struct.pack('<II', 32, 2) + dma + struct.pack('<II', 0, 0)
        out += struct.pack('<III', sum(c for _, c, _ in recs), 0, len(words))
        out += struct.pack(f'<{len(words)}I', *words) + struct.pack('<II', 0, 0)
    return out


class CallProfile(unittest.TestCase):
    def setUp(self):
        chip = bytearray(0x400)
        chip[0x100:0x106] = bytes.fromhex('4eb900000200')  # jsr $200
        chip[0x106:0x108] = bytes.fromhex('4e71')
        chip[0x200:0x202] = bytes.fromhex('4e71')
        chip[0x202:0x204] = bytes.fromhex('4e75')          # rts
        chip[0x300:0x302] = bytes.fromhex('4e73')          # rte
        self.chip = bytes(chip)
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, fields):
        p = os.path.join(self.dir.name, name)
        with open(p, 'wb') as f:
            f.write(trace(fields, self.chip))
        return p

    def test_calls_interrupts_and_chunks(self):
        r = Reduction(marks={'callee': 0x200, 'ret': 0x106}, tally={0x200, 0x202})
        r.feed(self.write('a.bin', [[(0x100, 20, 0x1000), (0x200, 8, 0xffc)]]))
        # The call stack carries into the next chunk; an interrupt nests under the callee.
        r.feed(self.write('b.bin', [[(GAP, 30, 0xffc), (0x300, 10, 0xff6), (0x202, 16, 0xffc),
                                     (0x106, 4, 0x1000), (None, 50, 0x1000)]]))
        self.assertEqual(r.stacks[()], 24)
        self.assertEqual(r.stacks[(0x200,)], 24)
        self.assertEqual(r.stacks[(0x200, ('irq', 0x300))], 10)
        self.assertEqual(r.stacks[(0x200, 'exception')], 30)
        self.assertEqual(r.stacks[('stop',)], 50)
        self.assertEqual(r.total(), 138)
        self.assertEqual(r.inclusive()[0x200], 64)
        self.assertEqual([f['nopc'] for f in r.fields], [0, 50])
        self.assertEqual(r.events, [('callee', 20, 0), ('ret', 84, 24)])
        self.assertEqual(r.dma_shares(), {'free': 0.5, 'CPU': 0.5})
        self.assertIn('IRQ 0x300', r.tree(min_share=0))
        p = os.path.join(self.dir.name, 'r.pkl.gz')
        r.save(p)
        self.assertEqual(Reduction.load(p).stacks, r.stacks)


if __name__ == '__main__':
    unittest.main()
