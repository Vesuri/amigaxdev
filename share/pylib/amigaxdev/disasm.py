"""objdump over memory dumps.

  python3 -m amigaxdev.disasm dis DUMP BASE START END
      disassemble [START,END) of a memory dump taken at BASE (objdump's own lines)
  python3 -m amigaxdev.disasm disd DUMP BASE HUNKBASE START END
      the same by hunk offset: `offset  bytes  instruction`
  python3 -m amigaxdev.disasm hotspots [--label NAME] TRACE DUMP BASE HUNKBASE OFF[,OFF...] [SPAN]
      hottest instructions of the routines at hunk offsets OFF (hex), with disassembly, as % of
      all traced cycles; NAME labels the region in the headings (default `hunk`)

Numbers take any Python base prefix; hotspots' OFF list is hex without one.  `--cpu 68020`
(before the command's arguments) picks objdump's machine; the default is 68000.
"""
import collections
import subprocess
import sys

from . import barto
from .env import tool


def objdump(dump, base, start, stop, cpu='68000'):
    return subprocess.run([tool('objdump'), '-D', '-b', 'binary', '-m', f'm68k:{cpu}',
                           f'--adjust-vma={base:#x}', f'--start-address={start:#x}',
                           f'--stop-address={stop:#x}', dump],
                          capture_output=True, text=True, check=True).stdout


def dis(dump, base, start, stop, cpu='68000'):
    """objdump's lines after the first label, as dis.sh printed them."""
    lines = objdump(dump, base, start, stop, cpu).split('\n')
    for i, l in enumerate(lines):
        if l.endswith('>:'):
            return '\n'.join(lines[i + 1:])
    return ''


def records(dump, base, hunkbase, start, end, cpu='68000'):
    """(hunk offset, raw bytes column, instruction text) for [hunkbase+start, hunkbase+end)."""
    for l in objdump(dump, base, hunkbase + start, hunkbase + end, cpu).split('\n'):
        if ':\t' in l and l.strip()[0] in '0123456789abcdef':
            a, rest = l.split(':', 1)
            parts = rest.split('\t')
            yield int(a, 16) - hunkbase, parts[1], ' '.join(parts[2:])


def disd(dump, base, hunkbase, start, end, cpu='68000'):
    for off, raw, text in records(dump, base, hunkbase, start, end, cpu):
        print(f'{off:05x}  {raw:<22} {text}')


def hotspots(trace, dump, base, hunkbase, offs, span=0x400, label='hunk', cpu='68000', top=14):
    t = barto.load(trace)
    pcs = collections.Counter()
    tot = 0
    for f in t.fields:
        for pc, c, r in t.instructions(f):
            tot += c
            if pc is not None:
                pcs[pc - hunkbase] += c
    dis_ = {}
    for o in offs:
        for off, raw, text in records(dump, base, hunkbase, o, o + span, cpu):
            dis_[off] = text
        tot_fn = sum(c for p, c in pcs.items() if o <= p < o + span)
        print(f'\n== {label}:{o:05x} (+{span:#x}): {100 * tot_fn / tot:.2f}%')
        for p, c in sorted(((p, c) for p, c in pcs.items() if o <= p < o + span),
                           key=lambda x: -x[1])[:top]:
            print(f'  {100 * c / tot:5.2f}  {p:05x}  {dis_.get(p, "?")}')


def main(argv):
    cpu, label = '68000', 'hunk'
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    while args and args[0] in ('--cpu', '--label'):
        if args[0] == '--cpu':
            cpu = args[1]
        else:
            label = args[1]
        args = args[2:]
    n = lambda x: int(x, 0)
    if cmd == 'dis':
        sys.stdout.write(dis(args[0], *map(n, args[1:4]), cpu=cpu))
    elif cmd == 'disd':
        disd(args[0], *map(n, args[1:5]), cpu=cpu)
    elif cmd == 'hotspots':
        span = n(args[5]) if len(args) > 5 else 0x400
        hotspots(args[0], args[1], n(args[2]), n(args[3]), [int(x, 16) for x in args[4].split(',')],
                 span, label, cpu)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
