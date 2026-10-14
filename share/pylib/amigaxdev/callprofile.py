"""Reduce Barto traces to a call profile, chunk by chunk, so long windows fit on disk.

A `monitor profile` field is about 5 MB; a 1000-field window would be 5 GB. Trace at most 100
fields at a time, feed each file to `Reduction.feed`, delete it, and keep only the reduction:

    from amigaxdev.callprofile import Reduction
    red = Reduction(marks={'swap': 0x2a0bc})
    for start in range(0, fields, 100):
        ...capture CHUNK.bin...
        red.feed('CHUNK.bin'); os.unlink('CHUNK.bin')
    red.save('profile.pkl.gz')
    print(red.tree(label=hex))

The stub records no call stacks (its unwinder needs a trigger), so they are rebuilt here:
a frame is pushed at the first instruction after JSR/BSR (keyed by that entry PC) or after an
exception-entry gap (keyed `('irq', PC)`), with the SP seen there, and popped as soon as SP
rises above it. That survives tail jumps, stack fix-ups and PEA/RTS dispatch better than
matching RTS, but it assumes one stack: code that switches between USP and SSP (an OS game's
task and its interrupts) splits into separate roots. Feed chunks in order and without gaps;
cycles run between chunks are not traced and the call stack carries across them.

Kept per run: self cycles and executions per PC, cycles per call stack, per-field totals
(cycles, STOP/no-PC, exception gaps, DMA slot counts by type), and for each execution of a
`marks` PC its trace position (cumulative traced cycles) and the running total of cycles spent
at the `tally` PCs so far (a wait loop, a STOP), so per-interval costs need no second pass.
"""
import collections
import gzip
import pickle
import struct

from . import barto

DMA_NAMES = {0: 'free', 1: 'refresh', 2: 'CPU', 3: 'copper', 4: 'audio', 5: 'blitter',
             6: 'bitplane', 7: 'sprite', 8: 'disk'}


def _opkind(t, pc, cache):
    """1 for JSR/BSR, else 0, from the trace's memory snapshots (code must not move)."""
    k = cache.get(pc)
    if k is None:
        if 0xc00000 <= pc < 0xc00000 + len(t.slow):
            m, o = t.slow, pc - 0xc00000
        elif pc < len(t.chip):
            m, o = t.chip, pc
        elif pc >= 0xf80000:
            m, o = t.rom, pc - 0xf80000
        else:
            m, o = b'', 0
        w = struct.unpack_from('>H', m, o)[0] if o + 2 <= len(m) else 0
        k = 1 if (w & 0xffc0) == 0x4e80 or (w & 0xff00) == 0x6100 else 0
        cache[pc] = k
    return k


class Reduction:
    def __init__(self, marks=None, tally=()):
        self.marks = dict(marks or {})       # name -> PC whose executions are timestamped
        self.tally = set(tally)              # PCs whose cycles accumulate into self.tallied
        self.self = collections.Counter()    # PC -> cycles
        self.counts = collections.Counter()  # PC -> executions
        self.stacks = collections.Counter()  # tuple of frames -> cycles
        self.fields = []                     # per-field dicts
        self.events = []                     # (name, position, tallied) in execution order
        self.pos = self.tallied = 0
        self._stack, self._sps, self._pend = (), (), 0

    def feed(self, trace):
        """Add one capture (a path or a loaded barto.Trace); returns the Trace."""
        t = barto.load(str(trace)) if not isinstance(trace, barto.Trace) else trace
        if t.pc_base:
            raise ValueError('relative-PC traces (.pc-base) are not supported')
        d, u, cache = t.data, struct.unpack_from, {}
        stack, sps, pend, pos, tallied = self._stack, self._sps, self._pend, self.pos, self.tallied
        tally = self.tally
        stacks, selfc, counts, events = self.stacks, self.self, self.counts, self.events
        marks = {pc: name for name, pc in self.marks.items()}
        for f in t.fields:
            off, end = f.insn_off, f.insn_end
            tot = nopc = gap = 0
            while off < end:
                pc = None
                while True:
                    v = u('<I', d, off)[0]
                    off += 4
                    if v >= 0xffff0000:
                        break
                    if pc is None:
                        pc = v
                c = 0xffffffff - v
                sp = u('<I', d, off + 60)[0]
                off += 68
                tot += c
                pos += c
                if pc is None:
                    nopc += c
                    stacks[stack + ('stop',)] += c
                    continue
                if pc == 0x7fffffff:
                    gap += c
                    pend = 3
                    stacks[stack + ('exception',)] += c
                    continue
                while sps and sp > sps[-1]:
                    stack, sps = stack[:-1], sps[:-1]
                if pend == 1:
                    stack, sps = stack + (pc,), sps + (sp,)
                elif pend == 3:
                    stack, sps = stack + (('irq', pc),), sps + (sp,)
                if pc in marks:
                    events.append((marks[pc], pos - c, tallied))
                if pc in tally:
                    tallied += c
                selfc[pc] += c
                counts[pc] += 1
                stacks[stack] += c
                pend = _opkind(t, pc, cache)
            dma = collections.Counter(f.dma[i + 29] for i in range(0, len(f.dma), f.dma_size))
            self.fields.append(dict(cycles=f.cycles, idle=f.idle, total=tot, nopc=nopc, gap=gap,
                                    dma=dict(dma)))
        self._stack, self._sps, self._pend, self.pos, self.tallied = stack, sps, pend, pos, tallied
        return t

    # -- results -------------------------------------------------------------------------------

    def total(self):
        return sum(f['total'] for f in self.fields)

    def inclusive(self):
        """Counter: frame -> cycles of every stack that contains it (recursion counted once)."""
        incl = collections.Counter()
        for st, c in self.stacks.items():
            for fr in set(st):
                incl[fr] += c
        return incl

    def dma_shares(self):
        dma = collections.Counter()
        for f in self.fields:
            dma.update(f['dma'])
        n = sum(dma.values()) or 1
        return {DMA_NAMES.get(k, str(k)): v / n for k, v in sorted(dma.items())}

    def tree(self, label=hex, min_share=0.01, depth=8):
        """Inclusive call tree as text, children under 1% (min_share) hidden."""
        def lab(fr):
            if isinstance(fr, tuple):
                return 'IRQ ' + lab(fr[1])
            return fr if isinstance(fr, str) else label(fr)
        tot = self.total() or 1
        root = {}
        for st, c in self.stacks.items():
            node, n = root, None
            for fr in st[:depth]:
                n = node.setdefault(fr, [0, 0, {}])
                n[0] += c
                node = n[2]
            if n is not None and len(st) <= depth:
                n[1] += c
        lines = []

        def walk(node, ind):
            for fr, (c, s, ch) in sorted(node.items(), key=lambda x: -x[1][0]):
                if c / tot < min_share:
                    continue
                lines.append(f'{"  " * ind}{lab(fr):24} {c / tot * 100:6.2f}%  self {s / tot * 100:5.2f}%')
                walk(ch, ind + 1)
        walk(root, 0)
        return '\n'.join(lines)

    def save(self, path):
        with gzip.open(path, 'wb') as f:
            pickle.dump(self.__dict__, f)

    @classmethod
    def load(cls, path):
        r = cls.__new__(cls)
        with gzip.open(path, 'rb') as f:
            r.__dict__.update(pickle.load(f))
        return r
