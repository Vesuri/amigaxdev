#!/usr/bin/env python3
"""Decode a WHDLoad resload_Patch list inside a slave (no source needed).

  python3 -m amigaxdev.patchlist SLAVE LIST_OFFSET

LIST_OFFSET is the list's offset in the slave's code hunk (as in a disassembly of the hunk
loaded at 0). Prints `offset  command  argument`; P/PS/PSS destinations are slave offsets.
"""
import struct, sys

CMDS = ['END', 'R', 'P', 'PS', 'S', 'I', 'B', 'W', 'L', 'A', 'PA', 'NOP', 'C', 'CB', 'CW', 'CL',
        'PSS', 'NEXT', 'AB', 'AW', 'AL', 'DATA', 'ORB', 'ORW', 'ORL', 'GA']
# Argument bytes after the address, per command (DATA is variable).
ARGS = {'R': 0, 'P': 2, 'PS': 2, 'S': 2, 'I': 0, 'B': 2, 'W': 2, 'L': 4, 'A': 4, 'PA': 2, 'NOP': 2,
        'C': 2, 'CB': 0, 'CW': 0, 'CL': 0, 'PSS': 4, 'NEXT': 2, 'AB': 2, 'AW': 2, 'AL': 4,
        'ORB': 2, 'ORW': 2, 'ORL': 4, 'GA': 2}


def slave_code(path):
    d = open(path, 'rb').read()
    assert struct.unpack_from('>I', d, 0)[0] == 0x3f3
    n = struct.unpack_from('>I', d, 8)[0]
    off = 20 + 4 * n
    assert struct.unpack_from('>I', d, off)[0] & 0x3fffffff == 0x3e9
    size = struct.unpack_from('>I', d, off + 4)[0] * 4
    return d[off + 8:off + 8 + size]


def decode(code, start):
    o = start
    while True:
        w = struct.unpack_from('>H', code, o)[0]; o += 2
        cmd = CMDS[w & 0x3fff] if (w & 0x3fff) < len(CMDS) else f'?{w:#x}'
        if cmd == 'END':
            yield None, 'END', ''
            return
        if w & 0x8000:
            adr = struct.unpack_from('>H', code, o)[0]; o += 2
        else:
            adr = struct.unpack_from('>I', code, o)[0]; o += 4
        if cmd == 'DATA':
            n = struct.unpack_from('>H', code, o)[0]
            arg = code[o + 2:o + 2 + n].hex(); o += 2 + n + (n & 1)
        else:
            k = ARGS.get(cmd, 0)
            raw = code[o:o + k]; o += k
            if cmd in ('P', 'PS', 'PSS', 'NEXT', 'PA'):
                dest = start + struct.unpack_from('>h', raw, 0)[0]
                arg = f'slave:{dest:04x}' + (f' nops={struct.unpack_from(">H", raw, 2)[0]}'
                                              if cmd == 'PSS' else '')
            elif cmd == 'S':
                arg = f'{struct.unpack_from(">h", raw, 0)[0] + 2:#x}'  # stored as distance-2
            else:
                arg = raw.hex()
        yield adr, cmd, arg


if __name__ == '__main__':
    code = slave_code(sys.argv[1])
    for adr, cmd, arg in decode(code, int(sys.argv[2], 0)):
        print(f'{adr:06x}  PL_{cmd:<4} {arg}' if adr is not None else 'PL_END')
