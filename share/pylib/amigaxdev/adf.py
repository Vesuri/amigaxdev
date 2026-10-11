#!/usr/bin/env python3
"""List or extract files from an AmigaDOS OFS/FFS floppy image (880 KB .adf / WHDLoad Disk.N).

  python3 -m amigaxdev.adf DISK                    list: path, size, first data block
  python3 -m amigaxdev.adf DISK PATH OUT           extract one file
  python3 -m amigaxdev.adf DISK --all OUTDIR       extract every file

Read-only; for locating the game's executables on the WHDLoad disk images.
"""
import os, struct, sys

BS = 512


def blk(d, n):
    return d[n * BS:(n + 1) * BS]


def L(b, i):
    """Long i of a block, negative i counting from the end (as in the RKM)."""
    return struct.unpack_from('>I', b, i * 4 if i >= 0 else BS + i * 4)[0]


def name(b):
    n = b[BS - 80]
    return b[BS - 79:BS - 79 + n].decode('latin-1')


def walk(d, n=880, path=''):
    b = blk(d, n)
    for h in range(6, 6 + 72):
        e = L(b, h)
        while e:
            eb = blk(d, e)
            p = f'{path}/{name(eb)}' if path else name(eb)
            st = struct.unpack_from('>i', eb, BS - 4)[0]
            if st == 2:
                yield from walk(d, e, p)
            elif st == -3:
                yield p, e, L(eb, -47)
            e = L(eb, -4)


def read(d, hdr):
    ffs = d[3] & 1
    hb = blk(d, hdr)
    size, out, cur = L(hb, -47), [], hb
    while True:
        blocks = [L(cur, i) for i in range(77, 5, -1)][:L(cur, 2)]
        for n in blocks:
            out.append(blk(d, n) if ffs else blk(d, n)[24:24 + L(blk(d, n), 3)])
        ext = L(cur, -2)
        if not ext:
            break
        cur = blk(d, ext)
    return b''.join(out)[:size]


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    if len(sys.argv) == 2:
        print('label:', name(blk(d, 880)), 'FFS' if d[3] & 1 else 'OFS')
        for p, h, s in walk(d):
            print(f'{s:8d}  hdr {h:4d}  {p}')
    elif sys.argv[2] == '--all':
        for p, h, s in walk(d):
            o = os.path.join(sys.argv[3], p)
            os.makedirs(os.path.dirname(o) or '.', exist_ok=True)
            open(o, 'wb').write(read(d, h))
    else:
        h = {p.lower(): h for p, h, s in walk(d)}[sys.argv[2].lower()]
        open(sys.argv[3], 'wb').write(read(d, h))
