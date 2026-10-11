"""Reader for FS-UAE/Barto `monitor profile` trace files.

Layout (little-endian uint32 unless noted):
  fields, nsections, section bases[nsections], stack bounds (16 bytes)
  ROM, Chip, Slow snapshots: size + bytes each
  base clock, cycle unit
  per field: custom regs (size+bytes), AGA colours (size+bytes),
             DMA records (recsize, count, bytes), resource records (recsize, count, bytes),
             cycles, idle, nwords, instruction words, screenshot (size, kind, bytes)
  instruction record: one or more words < 0xffff0000 (first = PC; the rest are the
  return addresses of the stub's own call-stack sampling), then 0xffffffff-cost,
  then 17 registers (d0-d7, a0-a7, sr).

A trace file with a sibling NAME.pc-base (one integer) has RAM PCs stored relative to the
profiler window; instructions() adds that base back.  capture.json next to a set of traces
splits them into independent captures (capture_part_starts).
"""
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Field:
    index: int
    custom: bytes
    dma_size: int
    dma: memoryview
    cycles: int
    idle: int
    insn_off: int
    insn_end: int
    shot_kind: int
    shot: bytes
    aga_colors: bytes = b''


@dataclass
class Trace:
    data: memoryview
    sections: list
    rom: bytes
    chip: bytes
    slow: bytes
    fields: list = field(default_factory=list)
    pc_base: int = 0

    def instructions(self, f):
        """Yield (pc, cost, regs) for every record of field f.

        None means no PC was recorded (the CPU is stopped, STOP).  0x7fffffff denotes cycles
        between instrumented instructions (interrupt handling or other CPU overhead), not
        necessarily an interrupt; the gap and the following instruction share the same register
        snapshot.
        """
        d, off, end = self.data, f.insn_off, f.insn_end
        u = struct.unpack_from
        regs = struct.Struct('<17I').unpack_from
        base = self.pc_base
        while off < end:
            pc = None
            while True:
                v = u('<I', d, off)[0]
                off += 4
                if v >= 0xffff0000:
                    break
                if pc is None:
                    pc = v
            # Barto stores RAM PCs relative to the profiler window, but physical Kickstart PCs
            # and the interrupt marker stay absolute.  Registers are absolute.
            if base and pc is not None and pc != 0x7fffffff and not 0xf80000 <= pc < 0x1000000:
                pc += base
            cost = 0xffffffff - v
            r = regs(d, off)
            off += 68
            yield pc, cost, r


def load(path):
    data = memoryview(open(path, 'rb').read())
    off = 0

    def w():
        nonlocal off
        v = struct.unpack_from('<I', data, off)[0]
        off += 4
        return v

    def blob():
        nonlocal off
        n = w()
        b = bytes(data[off:off + n])
        off += n
        return b

    nfields = w()
    nsec = w()
    sections = [w() for _ in range(nsec)]
    off += 16
    rom, chip, slow = blob(), blob(), blob()
    w(), w()
    t = Trace(data, sections, rom, chip, slow)
    for i in range(nfields):
        custom = blob()
        aga_colors = blob()
        dsize, dcount = w(), w()
        dma = data[off:off + dsize * dcount]
        off += dsize * dcount
        rsize, rcount = w(), w()
        off += rsize * rcount
        cycles, idle, n = w(), w(), w()
        ioff = off
        off += 4 * n
        ssize, skind = w(), w()
        shot = bytes(data[off:off + ssize])
        off += ssize
        t.fields.append(Field(i, custom, dsize, dma, cycles, idle, ioff, ioff + 4 * n, skind, shot,
                              aga_colors))
    assert off == len(data), (off, len(data))
    # Explicit metadata: old LLDB captures use base zero regardless of section bases.
    pc_base_path = Path(path).with_suffix('.pc-base')
    if pc_base_path.exists():
        t.pc_base = int(pc_base_path.read_text().strip(), 0)
        assert 0 <= t.pc_base < 0xffff0000, 'invalid profiler PC base'
    return t


def last_screenshot(path):
    """(kind, bytes) of the last field's screenshot, without decoding the instruction words."""
    f = load(path).fields
    return (f[-1].shot_kind, f[-1].shot) if f else None


def capture_part_starts(directory, trace):
    """Field indices that start independent captures; never bridge their gaps."""
    metadata = Path(directory) / 'capture.json'
    parts = json.loads(metadata.read_text())['parts'] if metadata.exists() else [len(trace.fields)]
    assert all(n > 0 for n in parts) and sum(parts) == len(trace.fields), parts
    starts, offset = set(), 0
    for n in parts:
        starts.add(offset)
        offset += n
    return starts
