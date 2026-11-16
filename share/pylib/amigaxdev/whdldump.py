"""Read the files WHDLoad's CoreDump writes: a crash report, registers and memory by address.

  python3 -m amigaxdev.whdldump [OPTIONS] DIR                summary of the selected report
  python3 -m amigaxdev.whdldump [OPTIONS] DIR read ADDR [N]  hex dump of N bytes (default $100)
  python3 -m amigaxdev.whdldump [OPTIONS] DIR dis [ADDR [N]] objdump of N bytes (default: PC-$20, $40)
  python3 -m amigaxdev.whdldump [OPTIONS] DIR reports        the reports appended to .whdl_register

  --report N        the Nth report in .whdl_register (0 first, negative from the end; default -1)
  --json            print the summary (or `reports`) as JSON
  --seg A,B,...     load addresses of the program's hunks 0, 1, ...: PC, frame and stack
                    return addresses are shown as `hunk N +$offset`; `A:SIZE` gives a size
                    (otherwise read from LoadSeg's longword at A-8 when it is in the dump)
  --hunk0 A         hunk 0's address; follow LoadSeg's BPTR chain at base-4 for the rest
  --cpu 680x0       objdump's machine (default: from the dump's AttnFlags)
  --stack N         bytes of stack scanned for return addresses (default $200)

DIR holds `.whdl_register` (text, appended per run), `.whdl_memory` (BaseMem), `.whdl_expmem`
(ExpMem) and `.whdl_dump` (IFF FORM WHDD with HEAD, TERM, OPT, CPU, CUST, CIAA, CIAB, SLAV,
MEM, EMEM, COLS chunks; layout in $WHDLOAD/Include/whddump.i).  Any subset works: `.whdl_dump`
alone has everything except the stack text; the report alone gives registers but no memory.
The binary files are rewritten per run, so they belong to the last report only.

ADDR is an expression of numbers (`$`/`0x` hex, else Python ints), register names (`pc`, `a7`,
`usp`, ...) and `hN` (hunk N's base, with --seg/--hunk0), joined by + and -: `h1+$40`, `a1-$26c`.

Python: `Dump(dir).read(addr, n)`, `.byte/.word/.long(addr)`, `.reg('a7')`, `.where(addr)`,
`.frame()`, `.return_addresses()`, `.summary()`.  Everything read is data; nothing in a dump is run.
"""
import argparse
import datetime
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

# --- text report ------------------------------------------------------------------------------

_ESC = re.compile(r'(?:\x9b|\x1b\[)[0-9;]*[A-Za-z]')
_HEADER = re.compile(r'^\*{3,}\s+(\S+ \S+)\s+\*+([0-9.]+)\*+\s*$')
_RANGE = re.compile(r'^(Resload|Slave|ExpMem|BaseMem)\s+([0-9A-Fa-f]+)\s+-\s+([0-9A-Fa-f]+)\s+'
                    r'\(\s*([\d,]+)\)\s+at\s+([0-9A-Fa-f]+)(.*)$')
_PAIR = re.compile(r'(\w+)=\s*([%$]?[0-9A-Fa-f]+)')
_HEXLINE = re.compile(r'^\$([0-9A-Fa-f]+)((?:\s+[0-9A-Fa-f]{4,8})+)\s*$')
_DISLINE = re.compile(r'^\$([0-9a-fA-F]{8}) (.*)$')

CIA_BINARY = ('cra', 'crb', 'pra', 'prb', 'ddra', 'ddrb')
# The report's names for what the binary dump calls these (the read registers, port outputs).
TEXT_CUSTOM = {'intena': 'INTENAR', 'intreq': 'INTREQR', 'dmacon': 'DMACONR', 'adkcon': 'ADKCONR'}
TEXT_CIA = {'pra': 'prao', 'prb': 'prbo'}


def strip_escapes(text):
    """The report without its CSI (0x9B) or ESC[ highlighting."""
    return _ESC.sub('', text)


def _num(s):
    s = s.strip()
    if s.startswith('%'):
        return int(s[1:], 2)
    if s.startswith('$'):
        return int(s[1:], 16)
    return int(s, 16)


def split_reports(text):
    """The raw reports in an appended .whdl_register, oldest first (escapes kept)."""
    out, cur = [], None
    for line in text.splitlines():
        if _HEADER.match(strip_escapes(line)):
            cur = [line]
            out.append(cur)
        elif cur is not None:
            cur.append(line)
    return ['\n'.join(r) for r in out]


def parse_termination(text):
    """Fields of WHDLoad's termination message: exception, address, task, program offset, ..."""
    t = ' '.join(text.split())
    out = {'text': t}
    m = re.search(r'Exception "([^"]*)" \(\$([0-9A-Fa-f]+)\)', t)
    if m:
        code = int(m.group(2), 16)
        out['exception'] = {'name': m.group(1), 'code': code, 'format': code >> 12,
                            'offset': code & 0xfff, 'vector': (code & 0xfff) // 4}
    elif t.startswith('DEBUG'):
        out['debug'] = True
    m = re.search(r'(?:\bat|PC =) \$([0-9A-Fa-f]+)', t)
    if m:
        out['address'] = int(m.group(1), 16)
    m = re.search(r"Task '([^']*)'", t)
    if m:
        out['task'] = m.group(1)
    m = re.search(r"Prg '([^']*)' Off \$([0-9A-Fa-f]+)", t)
    if m:
        out['program'] = {'name': m.group(1), 'offset': int(m.group(2), 16)}
    m = re.search(r'\b(BaseMem|ExpMem|Slave|Resload) \$([0-9A-Fa-f]+)\)', t)
    if m:
        out['region'] = {'name': m.group(1), 'offset': int(m.group(2), 16)}
    m = re.search(r'\b(Byte|Word|Long|Line|Quad)\s+(Read|Write|Fetch)\s+(?:from|to|at)\s+\$([0-9A-Fa-f]+)', t)
    if m:
        out['access'] = {'size': m.group(1), 'kind': m.group(2), 'address': int(m.group(3), 16)}
    return out


def parse_report(raw):
    """One .whdl_register report as a dict (see the module doc for the fields)."""
    lines = [strip_escapes(l).rstrip() for l in raw.splitlines()]
    r = {'regions': {}, 'disassembly': [], 'frame': None, 'stack': None, 'registers': {},
         'custom': {}, 'ciaa': {}, 'ciab': {}, 'attn': None, 'termination': None}
    m = _HEADER.match(lines[0])
    r['time'], r['version'] = m.group(1), m.group(2)
    state, term, hexblock = 'head', [], None
    for line in lines[1:]:
        s = line.strip()
        m = re.match(r"^Slave='([^']*)' \(([\d,]+) bytes\)", s)
        if m:
            r['slave'] = {'name': m.group(1), 'file_size': int(m.group(2).replace(',', ''))}
            continue
        m = _RANGE.match(s)
        if m:
            name, lo, hi, n, at, rest = m.groups()
            reg = {'start': int(lo, 16), 'end': int(hi, 16),
                   'size': int(n.replace(',', '')), 'physical': int(at, 16)}
            for k, v in _PAIR.findall(rest):
                reg[k] = _num(v)
            r['regions'][name] = reg
            if 'BaseMemSize' in reg:
                r['regions']['BaseMem'] = {'start': 0, 'end': reg['BaseMemSize'],
                                           'size': reg['BaseMemSize'], 'physical': 0}
            continue
        if s.startswith('attn='):
            m = re.match(r'attn=([0-9A-Fa-f]+)\(([^)]*)\)', s)
            if m:
                r['attn'] = int(m.group(1), 16)
                r['attn_text'] = m.group(2)
            r['flags'] = {k: v for k, v in re.findall(r'(\w+)=(-?\w+)', s) if k != 'attn'}
            continue
        if s.startswith('setcpu='):
            m = re.match(r'setcpu=([0-9A-Fa-f]+)\(([^)]*)\)', s)
            if m:
                r['setcpu'] = {'value': int(m.group(1), 16), 'text': m.group(2)}
            state = 'term'
            continue
        if state == 'term':
            if _DISLINE.match(s) or s in ('exception stackframe:', 'regular stack:') or \
                    s.startswith(('Dx ', '---0---')):
                state = 'body'
            else:
                if s:
                    term.append(s)
                continue
        if s == 'exception stackframe:':
            r['frame'] = hexblock = {'address': None, 'bytes': b''}
            continue
        if s == 'regular stack:':
            r['stack'] = hexblock = {'address': None, 'bytes': b''}
            continue
        m = _DISLINE.match(s)
        if m and hexblock is None and not _HEXLINE.match(s):
            r['disassembly'].append((int(m.group(1), 16), ' '.join(m.group(2).split())))
            continue
        m = _HEXLINE.match(s)
        if m and hexblock is not None:
            if hexblock['address'] is None:
                hexblock['address'] = int(m.group(1), 16)
            hexblock['bytes'] += bytes.fromhex(''.join(m.group(2).split()))
            continue
        if not s:
            hexblock = None
            continue
        hexblock = None
        if s.startswith(('Dx ', 'Ax ')):
            vals = [int(v, 16) for v in s.split()[1:]]
            for i, v in enumerate(vals):
                r['registers'][f'{s[0].lower()}{i}'] = v
            continue
        if 'ciaa:' in s:
            state = 'cia'
            continue
        if state == 'cia':
            seen = set()
            for k, v, latch in re.findall(r'(\w+)=([0-9A-Fa-f]+)(?:<([0-9A-Fa-f]+))?', s):
                cia = r['ciab'] if k in seen else r['ciaa']
                seen.add(k)
                cia[TEXT_CIA.get(k, k)] = int(v, 2) if k in CIA_BINARY else int(v, 16)
                if latch:
                    cia[k + '_latch'] = int(latch, 16)
            continue
        dotted = re.findall(r'(\w+?)\.+([0-9A-Fa-f]{4})\b', s)
        if s.startswith(('intena=', 'intreq=')) or dotted:
            state = 'custom'
        if state == 'custom':
            for k, v in _PAIR.findall(s) + dotted:
                r['custom'][TEXT_CUSTOM.get(k, k.upper())] = _num(v)
            continue
        for k, v in _PAIR.findall(s):
            r['registers'][k.lower()] = _num(v)
    r['termination'] = parse_termination(' '.join(term)) if term else None
    return r


# --- binary dump ------------------------------------------------------------------------------

CPU_FIELDS = (['d%d' % i for i in range(8)] + ['a%d' % i for i in range(7)] +
              ['pc', 'usp', 'ssp', 'msp'])
CPU_TAIL = ('vbr', 'caar', 'cacr', 'tt0', 'tt1', 'dtt0', 'dtt1', 'itt0', 'itt1', 'pcr', 'buscr')
# The CPU chunk's control registers that each CPU has (the others hold leftovers).
CPU_CONTROL = {
    '68000': ('sr', 'usp', 'ssp'),
    '68010': ('sr', 'usp', 'ssp', 'vbr', 'sfc', 'dfc'),
    '68020': ('sr', 'usp', 'isp', 'msp', 'vbr', 'sfc', 'dfc', 'cacr', 'caar'),
    '68030': ('sr', 'usp', 'isp', 'msp', 'vbr', 'sfc', 'dfc', 'cacr', 'caar', 'tt0', 'tt1', 'tc',
              'crp', 'srp', 'mmusr'),
    '68040': ('sr', 'usp', 'isp', 'msp', 'vbr', 'sfc', 'dfc', 'cacr', 'tc', 'urp', 'srp', 'mmusr',
              'dtt0', 'dtt1', 'itt0', 'itt1'),
    '68060': ('sr', 'usp', 'isp', 'vbr', 'sfc', 'dfc', 'cacr', 'tc', 'urp', 'srp', 'dtt0', 'dtt1',
              'itt0', 'itt1', 'pcr', 'buscr'),
}


def parse_iff(data):
    """{chunk id: bytes} of a FORM WHDD file; ValueError if it is not one."""
    if len(data) < 12 or data[:4] != b'FORM' or data[8:12] != b'WHDD':
        raise ValueError('not an IFF FORM WHDD file')
    end = min(len(data), 8 + struct.unpack_from('>I', data, 4)[0])
    chunks, o = {}, 12
    while o + 8 <= end:
        cid, n = struct.unpack_from('>4sI', data, o)
        if o + 8 + n > end:
            raise ValueError(f'chunk {cid!r} at {o} runs past the end')
        chunks.setdefault(cid.decode('latin-1'), (o + 8, n))
        o += 8 + n + (n & 1)
    return chunks


def _cstr(b):
    return b.split(b'\0', 1)[0].decode('latin-1')


def parse_head(b):
    """The HEAD chunk (whddump.i warns that it changes between WHDLoad versions)."""
    if len(b) < 604:
        return None
    v = struct.unpack_from('>5I', b, 0)
    h = dict(zip(('base_mem_size', 'shadow_mem', 'term_reason', 'term_primary',
                  'term_secondary'), v))
    h['term_string'] = _cstr(b[20:276])
    v = struct.unpack_from('>10I', b, 276)
    h.update(zip(('last_blit_pc', 'expmem_log', 'expmem_phy', 'expmem_len', 'resload_log',
                  'resload_phy', 'resload_len', 'slave_log', 'slave_phy', 'slave_len'), v))
    h['slave_name'] = _cstr(b[316:572])
    days, mins, ticks, kn, rw, cs, cpu, ver, rev, build, fc, zpt = \
        struct.unpack_from('>5I5H2b', b, 572)
    stamp = datetime.datetime(1978, 1, 1) + datetime.timedelta(days=days, minutes=mins,
                                                               seconds=ticks // 50)
    h.update(datestamp=stamp.strftime('%d-%b-%y %H:%M:%S'), kn=kn, rw=rw, cs=cs, attn=cpu,
             version=f'{ver}.{rev}.{build}', fc=fc, zpt=zpt)
    return h


def parse_cpu(b):
    if len(b) < 268:
        return None
    v = struct.unpack_from('>19I', b, 0)
    c = dict(zip(CPU_FIELDS, v))
    c['sr'], c['sfc'], c['dfc'] = struct.unpack_from('>HBB', b, 76)
    c.update(zip(CPU_TAIL, struct.unpack_from('>11I', b, 80)))
    srp, crp, drp = (struct.unpack_from('>Q', b, o)[0] for o in (124, 132, 140))
    c.update(srp=srp, crp=crp, drp=drp)
    c['tc'], c['mmusr'], c['urp'] = struct.unpack_from('>3I', b, 148)
    c['fp'] = [b[160 + 12 * i:172 + 12 * i].hex() for i in range(8)]
    c['fpcr'], c['fpsr'], c['fpiar'] = struct.unpack_from('>3I', b, 256)
    return c


def parse_cia(b):
    if len(b) < 25:
        return None
    v = struct.unpack_from('>6B4H2I5B', b, 0)
    k = ('prai', 'prbi', 'prao', 'prbo', 'ddra', 'ddrb', 'ta', 'tb', 'ta_latch', 'tb_latch',
         'event', 'alarm', 'sdr', 'icr', 'icm', 'cra', 'crb')
    return dict(zip(k, v))


CUSTOM_NAMES = {}


def _names():
    base = ('BLTDDAT DMACONR VPOSR VHPOSR DSKDATR JOY0DAT JOY1DAT CLXDAT ADKCONR POT0DAT POT1DAT '
            'POTGOR SERDATR DSKBYTR INTENAR INTREQR DSKPTH DSKPTL DSKLEN DSKDAT REFPTR VPOSW '
            'VHPOSW COPCON SERDAT SERPER POTGO JOYTEST STREQU STRVBL STRHOR STRLONG BLTCON0 '
            'BLTCON1 BLTAFWM BLTALWM BLTCPTH BLTCPTL BLTBPTH BLTBPTL BLTAPTH BLTAPTL BLTDPTH '
            'BLTDPTL BLTSIZE BLTCON0L BLTSIZV BLTSIZH BLTCMOD BLTBMOD BLTAMOD BLTDMOD - - - - '
            'BLTCDAT BLTBDAT BLTADAT - SPRHDAT BPLHDAT DENISEID DSKSYNC COP1LCH COP1LCL COP2LCH '
            'COP2LCL COPJMP1 COPJMP2 COPINS DIWSTRT DIWSTOP DDFSTRT DDFSTOP DMACON CLXCON INTENA '
            'INTREQ ADKCON').split()
    for i, n in enumerate(base):
        if n != '-':
            CUSTOM_NAMES[2 * i] = n
    for ch in range(4):
        for j, n in enumerate(('LCH', 'LCL', 'LEN', 'PER', 'VOL', 'DAT')):
            CUSTOM_NAMES[0xa0 + 16 * ch + 2 * j] = f'AUD{ch}{n}'
    for i in range(8):
        CUSTOM_NAMES[0xe0 + 4 * i] = f'BPL{i + 1}PTH'
        CUSTOM_NAMES[0xe2 + 4 * i] = f'BPL{i + 1}PTL'
        CUSTOM_NAMES[0x110 + 2 * i] = f'BPL{i + 1}DAT'
        CUSTOM_NAMES[0x120 + 4 * i] = f'SPR{i}PTH'
        CUSTOM_NAMES[0x122 + 4 * i] = f'SPR{i}PTL'
        for j, n in enumerate(('POS', 'CTL', 'DATA', 'DATB')):
            CUSTOM_NAMES[0x140 + 8 * i + 2 * j] = f'SPR{i}{n}'
    for i, n in enumerate('BPLCON0 BPLCON1 BPLCON2 BPLCON3 BPL1MOD BPL2MOD BPLCON4 CLXCON2'.split()):
        CUSTOM_NAMES[0x100 + 2 * i] = n
    for i in range(32):
        CUSTOM_NAMES[0x180 + 2 * i] = f'COLOR{i:02d}'
    for i, n in enumerate(('HTOTAL HSSTOP HBSTRT HBSTOP VTOTAL VSSTOP VBSTRT VBSTOP SPRHSTRT '
                           'SPRHSTOP BPLHSTRT BPLHSTOP HHPOSW HHPOSR BEAMCON0 HSSTRT VSSTRT '
                           'HCENTER DIWHIGH BPLHMOD SPRHPTH SPRHPTL BPLHPTH BPLHPTL').split()):
        CUSTOM_NAMES[0x1c0 + 2 * i] = n
    CUSTOM_NAMES[0x1fc] = 'FMODE'


_names()


def parse_custom(b):
    """{register offset: (value, flags)} for registers WHDLoad marked readable or modified."""
    if len(b) < 0x400:
        return None
    vals = struct.unpack_from('>256H', b, 0)
    out = {}
    for i, v in enumerate(vals):
        f = b[0x200 + 2 * i]
        if f & 0x81:  # CUSTF_READ, CUSTF_MODI
            out[2 * i] = (v, f)
    return out


# --- frames and code --------------------------------------------------------------------------

def cpu_model(attn):
    """objdump machine for AttnFlags (AFB_68010..AFB_68060 = bits 0, 1, 2, 3, 7)."""
    if attn is None:
        return '68000'
    for bit, m in ((7, '68060'), (3, '68040'), (2, '68030'), (1, '68020'), (0, '68010')):
        if attn & (1 << bit):
            return m
    return '68000'


FRAME_WORDS = {0: 4, 1: 4, 2: 6, 3: 6, 4: 8, 7: 30, 8: 29, 9: 10, 0xa: 16, 0xb: 46}


def decode_frame(b, cpu='68010'):
    """The fields of an exception stack frame starting at its SR (68010 and later)."""
    if len(b) < 8:
        return None
    sr, pc, fv = struct.unpack_from('>HIH', b, 0)
    fmt = fv >> 12
    f = {'sr': sr, 'pc': pc, 'format': fmt, 'offset': fv & 0xfff, 'vector': (fv & 0xfff) // 4,
         'words': FRAME_WORDS.get(fmt)}
    w = lambda o: struct.unpack_from('>I', b, o)[0] if len(b) >= o + 4 else None
    if fmt in (2, 3):
        f['address'] = w(8)
    elif fmt == 4:
        f['ea'], f['fslw'] = w(8), w(12)
    elif fmt == 7:
        f['ea'] = w(8)
        if len(b) >= 14:
            f['ssw'] = struct.unpack_from('>H', b, 12)[0]
        f['fault_address'] = w(20)
    elif fmt in (0xa, 0xb):
        if len(b) >= 12:
            f['ssw'] = struct.unpack_from('>H', b, 10)[0]
        f['fault_address'] = w(16)
    return f


# Calls whose return address is the next instruction: (bytes before the return, mask, value)
_CALLS = ((2, 0xff00, 0x6100, lambda w: w & 0xff not in (0, 0xff)),  # bsr.b
          (4, 0xffff, 0x6100, None),  # bsr.w
          (6, 0xffff, 0x61ff, None),  # bsr.l
          (2, 0xfff8, 0x4e90, None),  # jsr (an)
          (4, 0xfff8, 0x4ea8, None),  # jsr d16(an)
          (4, 0xfff8, 0x4eb0, None),  # jsr d8(an,xn)
          (4, 0xffff, 0x4eb8, None),  # jsr abs.w
          (6, 0xffff, 0x4eb9, None),  # jsr abs.l
          (4, 0xffff, 0x4eba, None),  # jsr d16(pc)
          (4, 0xffff, 0x4ebb, None))  # jsr d8(pc,xn)


# --- the dump ---------------------------------------------------------------------------------

def parse_addr(text, dump=None):
    """An ADDR expression: numbers, register names and hN joined by + and -."""
    total = 0
    for sign, term in re.findall(r'([+-]?)\s*([^+\-\s]+)', text.strip()):
        t = term.lower()
        if t.startswith('$'):
            v = int(t[1:], 16)
        elif re.fullmatch(r'h\d+', t) and dump is not None:
            v = dump.hunks[int(t[1:])][0]
        elif dump is not None and dump.reg(t) is not None:
            v = dump.reg(t)
        else:
            v = int(t, 0)
        total += -v if sign == '-' else v
    return total & 0xffffffff


class Dump:
    """A CoreDump directory: the selected report, the binary state and the memory it maps."""

    def __init__(self, path, report=-1, segs=None, hunk0=None):
        """segs: hunk bases, or (base, size) pairs; hunk0: follow the seglist from there."""
        self.path = path
        self.warnings = []
        self.reports, self.report = [], None
        p = os.path.join(path, '.whdl_register')
        if os.path.exists(p):
            with open(p, 'rb') as f:
                self.reports = split_reports(f.read().decode('latin-1'))
            if self.reports:
                self.report_index = report % len(self.reports)
                self.report = parse_report(self.reports[self.report_index])
        self.head = self.cpu = self.custom = self.ciaa = self.ciab = None
        self.term = self.options = None
        self.regions = []  # (name, start, data)
        self._binary()
        self._memory_files()
        # The binary files are rewritten per capture: they belong to the last report only.
        self.current = not self.report or self.report_index == len(self.reports) - 1
        if not self.current:
            self.cpu = self.custom = self.ciaa = self.ciab = self.term = None
            if self.head or self.regions:
                self.warnings.append('the dumped memory is from the last capture, not from '
                                     'the selected report; registers are the report\'s')
        if self.report and self.head and self.report['time'] != self.head['datestamp'] and \
                self.report_index == len(self.reports) - 1:
            self.warnings.append(f"last report ({self.report['time']}) and .whdl_dump "
                                 f"({self.head['datestamp']}) are from different captures")
        self.hunks = []
        if segs:
            self.hunks = [(b, self._hunk_size(b)) if isinstance(b, int) else
                          (b[0], b[1] if b[1] is not None else self._hunk_size(b[0]))
                          for b in segs]
        elif hunk0 is not None:
            self.hunks = self.seglist(hunk0)

    # loading

    def _binary(self):
        p = os.path.join(self.path, '.whdl_dump')
        if not os.path.exists(p):
            return
        with open(p, 'rb') as f:
            data = f.read()
        try:
            ch = parse_iff(data)
        except ValueError as e:
            self.warnings.append(f'.whdl_dump: {e}')
            return
        get = lambda k: data[ch[k][0]:ch[k][0] + ch[k][1]] if k in ch else b''
        self.chunks = sorted(ch)
        self.head = parse_head(get('HEAD'))
        self.cpu = parse_cpu(get('CPU '))
        self.custom = parse_custom(get('CUST'))
        self.ciaa, self.ciab = parse_cia(get('CIAA')), parse_cia(get('CIAB'))
        self.term = _cstr(get('TERM')) if 'TERM' in ch else None
        self.options = _cstr(get('OPT ')) if 'OPT ' in ch else None
        h = self.head
        if 'MEM ' in ch:
            if h and h['base_mem_size'] != ch['MEM '][1]:
                self.warnings.append('HEAD BaseMemSize differs from the MEM chunk')
            self.regions.append(('BaseMem', 0, get('MEM ')))
        if 'EMEM' in ch:
            base = h['expmem_log'] if h else self._report_start('ExpMem')
            if base is not None:
                self.regions.append(('ExpMem', base, get('EMEM')))
        if 'SLAV' in ch:
            base = h['slave_log'] if h else self._report_start('Slave')
            if base is not None:
                self.regions.append(('Slave', base, get('SLAV')))

    def _report_start(self, name):
        r = self.report and self.report['regions'].get(name)
        return r['start'] if r else None

    def _memory_files(self):
        have = {n for n, _, _ in self.regions}
        for name, fn in (('BaseMem', '.whdl_memory'), ('ExpMem', '.whdl_expmem')):
            p = os.path.join(self.path, fn)
            if name in have or not os.path.exists(p):
                continue
            base = 0 if name == 'BaseMem' else (self.head['expmem_log'] if self.head
                                                else self._report_start('ExpMem'))
            if base is None:
                self.warnings.append(f'{fn}: no ExpMem address in the report')
                continue
            with open(p, 'rb') as f:
                self.regions.append((name, base, f.read()))

    # memory

    def ranges(self):
        """{name: (start, size)} of BaseMem, ExpMem, Slave and Resload, mapped or not."""
        out = {}
        if self.report:
            for n, r in self.report['regions'].items():
                out[n] = (r['start'], r['size'])
        h = self.head if self.current else None
        if h:
            out['BaseMem'] = (0, h['base_mem_size'])
            for n, k in (('ExpMem', 'expmem'), ('Resload', 'resload'), ('Slave', 'slave')):
                if h[k + '_len']:
                    out[n] = (h[k + '_log'], h[k + '_len'])
        for n, s, d in self.regions:
            out.setdefault(n, (s, len(d)))
        return out

    def where(self, addr):
        """('ExpMem', offset), ... for the range holding addr, else (None, addr)."""
        for n, (s, size) in sorted(self.ranges().items(), key=lambda x: -x[1][0]):
            if s <= addr < s + size:
                return n, addr - s
        return None, addr

    def mapped(self, addr, n=1):
        return any(s <= addr and addr + n <= s + len(d) for _, s, d in self.regions)

    def read(self, addr, n):
        """n bytes at an Amiga address; KeyError if any of them is outside the dumped memory."""
        for _, s, d in self.regions:
            if s <= addr and addr + n <= s + len(d):
                return d[addr - s:addr - s + n]
        raise KeyError(f'${addr:X}+{n} is not in the dumped memory')

    def byte(self, addr):
        return self.read(addr, 1)[0]

    def word(self, addr):
        return struct.unpack('>H', self.read(addr, 2))[0]

    def long(self, addr):
        return struct.unpack('>I', self.read(addr, 4))[0]

    # registers

    def registers(self):
        """d0-d7, a0-a7, pc, sr, usp, ssp/isp, msp and the control registers."""
        r = {}
        if self.report:
            r.update(self.report['registers'])
        if self.cpu:
            model = self.cpu_name()
            c = dict(self.cpu, isp=self.cpu['ssp'])
            keep = CPU_CONTROL[model] + ('pc',)
            r.update((k, c[k]) for k in tuple(CPU_FIELDS[:15]) + keep if k in c)
            if model >= '68040' or self.cpu['fpcr'] or self.cpu['fpsr'] or \
                    any(int(x, 16) for x in self.cpu['fp']):
                r.update(fpcr=c['fpcr'], fpsr=c['fpsr'], fpiar=c['fpiar'])
        sr = r.get('sr')
        if sr is not None:
            if not sr & 0x2000:
                sp = r.get('usp')
            elif sr & 0x1000:
                sp = r.get('msp')
            else:
                sp = r.get('isp', r.get('ssp'))
            if sp is not None:
                r['a7'] = sp
        return r

    def reg(self, name):
        name = name.lower()
        if name == 'sp':
            name = 'a7'
        return self.registers().get(name)

    def cpu_name(self):
        attn = self.head['attn'] if self.head else (self.report or {}).get('attn')
        return cpu_model(attn)

    # code

    def _hunk_size(self, base):
        """LoadSeg's allocation size at base-8, minus its 8 header bytes, when it looks sane."""
        try:
            n = self.long(base - 8)
        except KeyError:
            return None
        return n - 8 if 8 < n < 0x1000000 else None

    def seglist(self, hunk0, limit=256):
        """[(base, size)] following the BPTR chain at base-4 from hunk 0."""
        out, base = [], hunk0
        while base and len(out) < limit:
            out.append((base, self._hunk_size(base)))
            try:
                nxt = self.long(base - 4)
            except KeyError:
                self.warnings.append(f'seglist: ${base - 4:X} is not in the dumped memory')
                break
            base = (nxt << 2) + 4 if nxt else 0
        return out

    def hunk_of(self, addr):
        """(hunk, offset) for an address inside a known hunk, else None."""
        best = None
        for i, (b, size) in enumerate(self.hunks):
            if addr >= b and (size is None or addr < b + size):
                if best is None or b > self.hunks[best][0]:
                    best = i
        return (best, addr - self.hunks[best][0]) if best is not None else None

    def describe(self, addr):
        """`$924208 ExpMem+$B5208 hunk 2 +$AB90` style location."""
        out = f'${addr:X}'
        n, off = self.where(addr)
        if n:
            out += f' {n}+${off:X}'
        h = self.hunk_of(addr)
        if h:
            out += f' hunk {h[0]} +${h[1]:X}'
        return out

    def disassemble(self, start, n, cpu=None):
        """objdump's instruction lines for [start, start+n) of the dumped memory."""
        from .disasm import dis
        data = self.read(start, n)
        fd, tmp = tempfile.mkstemp(suffix='.bin')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            return dis(tmp, start, start, start + n, cpu or self.cpu_name())
        finally:
            os.unlink(tmp)

    def frame(self):
        """The decoded exception frame: from memory at the supervisor stack, else the report."""
        cpu = self.cpu_name()
        if cpu == '68000':
            return None
        rep = self.report and self.report.get('frame')
        if rep and rep['bytes']:
            f = decode_frame(rep['bytes'], cpu)
            if f:
                f['at'] = rep['address']
            return f
        regs = self.registers()
        for k in ('isp', 'ssp'):
            if regs.get(k) is not None and self.mapped(regs[k], 8):
                f = decode_frame(self.read(regs[k], 8), cpu)
                words = f['words'] or 4
                if self.mapped(regs[k], 2 * words):
                    f = decode_frame(self.read(regs[k], 2 * words), cpu)
                f['at'] = regs[k]
                return f
        return None

    def stack_bytes(self, n=0x200):
        """(address, bytes) of the stack at a7: dumped memory, else the report's stack lines."""
        a7 = self.reg('a7')
        if a7 is not None:
            for m in range(n, 0, -2):
                if self.mapped(a7, m):
                    return a7, self.read(a7, m)
        st = self.report and self.report.get('stack')
        if st and st['bytes']:
            return st['address'], st['bytes']
        return a7, b''

    def _is_call_return(self, ret):
        for back, mask, val, extra in _CALLS:
            if ret < back or not self.mapped(ret - back, 2):
                continue
            w = self.word(ret - back)
            if w & mask == val and (extra is None or extra(w)):
                return True
        return False

    def return_addresses(self, n=0x200):
        """[(stack address, value, verified)] for even longs on the stack that point just after
        a bsr/jsr (verified) or, when the code is not in the dump, into a known hunk."""
        at, b = self.stack_bytes(n)
        out = []
        if at is None:
            return out
        for o in range(0, len(b) - 3, 2):
            v = struct.unpack_from('>I', b, o)[0]
            if v & 1 or v < 8:
                continue
            if self.hunks and not self.hunk_of(v):
                continue
            if self.mapped(v - 6, 6):
                if self._is_call_return(v):
                    out.append((at + o, v, True))
            elif self.hunks and self.hunks[self.hunk_of(v)[0]][1] is not None:
                out.append((at + o, v, False))
        return out

    # summary

    def termination(self):
        if self.report and self.report.get('termination'):
            return self.report['termination']
        if self.term:
            return parse_termination(self.term)
        return None

    def summary(self, stack=0x200):
        rep = self.report or {}
        regs = self.registers()
        pc = regs.get('pc')
        t = self.termination()
        s = {'dir': self.path, 'reports': len(self.reports),
             'report_index': getattr(self, 'report_index', None),
             'time': rep.get('time') or (self.head or {}).get('datestamp'),
             'version': rep.get('version') or (self.head or {}).get('version'),
             'slave': rep.get('slave') or ({'name': self.head['slave_name']} if self.head else None),
             'cpu': self.cpu_name(), 'options': self.options,
             'ranges': {k: {'start': a, 'size': n} for k, (a, n) in self.ranges().items()},
             'mapped': [{'name': n, 'start': a, 'size': len(d)} for n, a, d in self.regions],
             'termination': t, 'registers': regs, 'warnings': self.warnings}
        if pc is not None:
            s['pc'] = self._loc(pc)
        if t and t.get('access'):
            s['access'] = dict(t['access'], **self._loc(t['access']['address']))
        f = self.frame()
        if f:
            s['frame'] = f
            for k in ('pc', 'address', 'fault_address', 'ea'):
                if f.get(k) is not None:
                    f[k + '_where'] = self.describe(f[k])
        s['hunks'] = [{'hunk': i, 'start': b, 'size': n} for i, (b, n) in enumerate(self.hunks)]
        s['returns'] = [{'at': a, 'value': v, 'where': self.describe(v), 'verified': ok}
                        for a, v, ok in self.return_addresses(stack)]
        at, b = self.stack_bytes(0x40)
        s['stack'] = {'address': at, 'longs': [struct.unpack_from('>I', b, o)[0]
                                                for o in range(0, len(b) - 3, 4)]}
        if self.custom is not None:
            s['custom'] = {CUSTOM_NAMES.get(o, f'{o:03X}'): v for o, (v, _) in self.custom.items()}
        elif rep.get('custom'):
            s['custom'] = rep['custom']
        s['ciaa'] = self.ciaa or rep.get('ciaa')
        s['ciab'] = self.ciab or rep.get('ciab')
        s['disassembly'] = rep.get('disassembly', [])
        return s

    def _loc(self, addr):
        n, off = self.where(addr)
        d = {'address': addr, 'region': n, 'offset': off if n else None}
        h = self.hunk_of(addr)
        if h:
            d['hunk'], d['hunk_offset'] = h
        return d


# --- CLI --------------------------------------------------------------------------------------

def _hexdump(d, start, n):
    data = d.read(start, n)
    lines = []
    for o in range(0, len(data), 16):
        row = data[o:o + 16]
        words = ' '.join(row[i:i + 4].hex().upper() for i in range(0, len(row), 4))
        text = ''.join(chr(c) if 32 <= c < 127 else '.' for c in row)
        lines.append(f'${start + o:08X}  {words:<35}  {text}')
    return '\n'.join(lines)


def format_summary(d, s):
    out = []
    w = out.append
    slave = s['slave'] or {}
    w(f"WHDLoad {s['version']}  {s['time']}  {slave.get('name', '?')}  CPU {s['cpu']}"
      + (f"  (report {s['report_index'] + 1} of {s['reports']})" if s['reports'] else ''))
    for msg in s['warnings']:
        w(f'warning: {msg}')
    rng = '  '.join(f"{k} ${v['start']:X}+${v['size']:X}" for k, v in
                    sorted(s['ranges'].items(), key=lambda x: x[1]['start']))
    w(f'ranges: {rng}')
    if s['options']:
        w(f"options: {s['options']}")
    t = s['termination']
    if t:
        w('')
        w(t['text'])
        e = t.get('exception')
        if e:
            w(f"exception: {e['name']}, vector {e['vector']} (${e['offset']:03X}), "
              f"frame format ${e['format']:X}")
    if 'pc' in s:
        w(f"PC {d.describe(s['pc']['address'])}")
        vec = t['exception']['vector'] if t and t.get('exception') else None
        if vec in (5, 6, 7) or vec is not None and 32 <= vec < 48:
            prev = [a for a, _ in s['disassembly'] if a < s['pc']['address']]
            if prev:
                w(f'   (a trap: the stacked PC follows the trapping instruction, '
                  f'{d.describe(prev[-1])})')
    if t and t.get('program'):
        w(f"program: '{t['program']['name']}' Off ${t['program']['offset']:X} (as WHDLoad "
          f"reports it)")
    if 'access' in s:
        a = s['access']
        w(f"access: {a['size']} {a['kind']} {d.describe(a['address'])}")
    r = s['registers']
    w('')
    for p in 'da':
        w('  '.join(f'{p}{i}={r[p + str(i)]:08X}' for i in range(8) if p + str(i) in r))
    ctl = [k for k in ('sr', 'usp', 'isp', 'ssp', 'msp', 'vbr', 'sfc', 'dfc', 'cacr', 'caar',
                       'tc', 'tt0', 'tt1', 'dtt0', 'dtt1', 'itt0', 'itt1', 'urp', 'srp', 'crp',
                       'mmusr', 'pcr', 'buscr', 'fpcr', 'fpsr', 'fpiar') if k in r]
    w('  '.join(f'{k}={r[k]:0{4 if k == "sr" else 1}X}' for k in ctl))
    f = s.get('frame')
    if f:
        w('')
        line = (f"frame at ${f['at']:X}: format ${f['format']:X} vector {f['vector']} "
                f"(${f['offset']:03X})  SR={f['sr']:04X}  PC {f['pc_where']}")
        for k in ('address', 'ea', 'fault_address'):
            if f.get(k) is not None:
                line += f'  {k}={f[k + "_where"]}'
        if f.get('ssw') is not None:
            line += f"  SSW={f['ssw']:04X}"
        w(line)
    if s['disassembly']:
        w('')
        pc = s['pc']['address'] if 'pc' in s else None
        dis = s['disassembly']
        i = next((k for k, (a, _) in enumerate(dis) if a == pc), None)
        sel = dis[max(0, i - 4):i + 5] if i is not None else dis[:9]
        for a, text in sel:
            h = d.hunk_of(a)
            hs = f'h{h[0]}+{h[1]:05X}' if h else ''
            w(f"{'>' if a == pc else ' '} ${a:08X} {hs:<10} {text}")
    elif 'pc' in s and d.mapped(s['pc']['address'], 0x20):
        w('')
        w(d.disassemble(s['pc']['address'], 0x20).rstrip())
    if s['hunks']:
        w('')
        w('hunks: ' + '  '.join(f"{h['hunk']}=${h['start']:X}" +
                                (f"+${h['size']:X}" if h['size'] else '') for h in s['hunks']))
    st = s['stack']
    if st['longs']:
        w('')
        w(f"stack at ${st['address']:X}:")
        for o in range(0, len(st['longs']), 8):
            w(f"  ${st['address'] + 4 * o:08X} " +
              ' '.join(f'{v:08X}' for v in st['longs'][o:o + 8]))
    if s['returns']:
        w('return addresses (after a bsr/jsr; ? = code not in the dump, unchecked):')
        for x in s['returns']:
            w(f"  ${x['at']:08X}  {x['where']}{'' if x['verified'] else '  ?'}")
    c = s.get('custom')
    if c:
        w('')
        keys = [k for k in ('DMACONR', 'INTENAR', 'INTREQR', 'ADKCONR', 'VPOSR', 'VHPOSR')
                if k in c]
        w('custom: ' + '  '.join(f'{k}={c[k]:04X}' for k in keys))
    for n in ('ciaa', 'ciab'):
        ci = s.get(n)
        if ci:
            w(f'{n}: ' + '  '.join(f'{k}={v:X}' for k, v in ci.items()))
    return '\n'.join(out)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, bytes):
        return x.hex()
    return x


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python3 -m amigaxdev.whdldump',
                                 description='Read a WHDLoad CoreDump directory.',
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n\n', 1)[1])
    ap.add_argument('dir')
    ap.add_argument('command', nargs='*', help='read ADDR [N] | dis [ADDR [N]] | reports')
    ap.add_argument('--report', type=int, default=-1)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--seg')
    ap.add_argument('--hunk0')
    ap.add_argument('--cpu')
    ap.add_argument('--stack', default='0x200')
    a = ap.parse_intermixed_args(argv)
    if not os.path.isdir(a.dir):
        ap.error(f'{a.dir} is not a directory')
    segs = [tuple(parse_addr(y) for y in x.split(':', 1)) if ':' in x else parse_addr(x)
            for x in a.seg.split(',')] if a.seg else None
    d = Dump(a.dir, a.report, segs=segs, hunk0=parse_addr(a.hunk0) if a.hunk0 else None)
    if not d.reports and not d.regions and d.head is None:
        sys.exit(f'whdldump: no .whdl_register, .whdl_dump, .whdl_memory or .whdl_expmem in {a.dir}')
    cmd = a.command
    try:
        if not cmd:
            s = d.summary(parse_addr(a.stack))
            print(json.dumps(_jsonable(s), indent=1) if a.json else format_summary(d, s))
        elif cmd[0] == 'reports':
            rows = []
            for i, raw in enumerate(d.reports):
                r = parse_report(raw)
                rows.append({'index': i, 'time': r['time'], 'version': r['version'],
                             'slave': (r.get('slave') or {}).get('name'),
                             'termination': (r['termination'] or {}).get('text')})
            if a.json:
                print(json.dumps(rows, indent=1))
            for x in rows if not a.json else ():
                print(f"{x['index']:3d}  {x['time']}  {x['slave']}  {x['termination']}")
        elif cmd[0] == 'read' and len(cmd) in (2, 3):
            n = parse_addr(cmd[2], d) if len(cmd) > 2 else 0x100
            print(_hexdump(d, parse_addr(cmd[1], d), n))
        elif cmd[0] == 'dis' and len(cmd) <= 3:
            start = parse_addr(cmd[1], d) if len(cmd) > 1 else (d.reg('pc') or 0) - 0x20
            n = parse_addr(cmd[2], d) if len(cmd) > 2 else 0x40
            text = d.disassemble(start & ~1, n, a.cpu)
            for line in text.splitlines():
                m = re.match(r'\s*([0-9a-f]+):', line)
                h = d.hunk_of(int(m.group(1), 16)) if m else None
                print(f'h{h[0]}+{h[1]:05X} {line}' if h else line)
        else:
            ap.error('unknown command: ' + ' '.join(cmd))
    except KeyError as e:
        sys.exit(f'whdldump: {e.args[0]}')
    except subprocess.CalledProcessError as e:
        sys.exit(f'whdldump: objdump failed: {e.stderr}')


if __name__ == '__main__':
    main()
