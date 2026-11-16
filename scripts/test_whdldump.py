#!/usr/bin/env python3
"""amigaxdev.whdldump on synthetic CoreDump files: python3 scripts/test_whdldump.py

WHDLDUMP_SAMPLE=DIR also runs the reader over a real CoreDump directory (not part of the repo).
"""
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

PYLIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'share', 'pylib')
sys.path.insert(0, PYLIB)
from amigaxdev import whdldump  # noqa: E402
from amigaxdev.env import tool  # noqa: E402

B, E = '\x9b1m', '\x9b22m'
EXP, EXPLEN = 0x20000, 0x2000
SLAVE = 0x30000
H0, H1 = EXP + 0x108, EXP + 0x408  # hunk bases (LoadSeg: size at -8, BPTR next at -4)
PC = H1 + 0x20
SP = EXP + 0x1800
ISP = EXP + 0x1f00


def report(time, pc, frame_line, stack_line, name='Test.Slave'):
    return f"""
************************ {time} **********************20.1.7190**
Slave='{name}' (1,234 bytes)
Resload     40000 -    40100 (      256) at 40000  GL=40200
Slave       {SLAVE:X} -    {SLAVE + 0x40:X} (       64) at {SLAVE:X}  BaseMemSize=1000
ExpMem      {EXP:X} -    {EXP + EXPLEN:X} (    8,192) at {EXP:X}
attn=207(UAE,30) fc=-1 kn=0 zpt=-1 ep=0 ei=0
setcpu=3B3E(SS,BC,SB,DC,IC,SCB,ECB,BWT)

Exception "Integer Divide by Zero" ($2014) at ${pc:X} (Task 'Initial CLI',
ExpMem ${pc - EXP:X}) occurred.

${pc - 4:08x} divs         d2,d1
{B}${pc:08x} move.w       d4,d5
{E}${pc + 2:08x} rts

exception stackframe:
{frame_line}
regular stack:
{stack_line}

    ---0---  ---1---  ---2---  ---3---  ---4---  ---5---  ---6---  ---7---
Dx        0       17    60000   9480F0 FFFF0000        0        9       17
Ax    {H1:X}    {EXP + 0x1000:X}        1        2        3        4        5

                 TTSM III   XNZVC
{B}PC=  {pc:X}{E}  SR=%0000000000000100{B}  USP={SP:X}  {E}ISP={ISP:X}  MSP=19F800
VBR=9F0B40  SFC=5  DFC=5  CACR=2111  CAAR=0  TT0=0  TT1=0
TC=0  CRP=100000000  SRP=100000000  MMUSR=0

         MEDRAAAABVCPSDT          YZ  PMRCBSDAAAA
intena=%{B}0110000000111100{E} dmacon=%{B}0000001111010000{E} adkcon=$1100
intreq=%{B}0000000001000000{E}
vposr....A300  vhposr...0275  joy0dat..0103  joy1dat..0000  clxdat...8000
   ciaa:     PI ROPS\t\t   ciab:     PI ROPS
\tcra={B}00000000{E}  ta=21FF<21FF\t   cra={B}00000000{E}  ta=FFFF<FFFF
\t    AII ROPS\t\t\t    AII ROPS
\tcrb={B}00000001{E}  tb=6B05<FFFF\t   crb={B}10000000{E}  tb=FFFF<FFFF
\t    10RTWCLO\t  parallel\t    DRCCDSOY      M3210HDS
\tpra={B}11111110{E}  prb={B}11111111{E}      pra={B}11111111{E}  prb={B}11111111{E}
       ddra={B}00000011{E} ddrb={B}00000000{E}     ddra={B}11000000{E} ddrb={B}11111111{E}
       event=0001AA  icr=00  sdr=3F    event=00013C  icr=04  sdr=00
"""


def expmem():
    m = bytearray(EXPLEN)
    put = lambda a, fmt, *v: struct.pack_into(fmt, m, a - EXP, *v)
    put(H0 - 8, '>II', 0x300 + 8, (H1 - 4) >> 2)  # hunk 0: size, BPTR to hunk 1
    put(H1 - 8, '>II', 0x100 + 8, 0)  # hunk 1: size, end of the chain
    put(H1 + 0x10, '>HH', 0x6100, 0x0010)  # bsr.w: returns to H1+$14
    put(H1 + 0x18, '>H', 0x4e90)  # jsr (a0): returns to H1+$1A
    put(PC - 4, '>HH', 0x83c2, 0x4e75)  # divs d2,d1; rts
    put(PC, '>HH', 0x3a04, 0x4e75)  # move.w d4,d5; rts
    put(SP, '>IIII', 0x12345678, H1 + 0x14, H1 + 0x1a, H1 + 0x16)  # 2 calls, 1 non-call
    put(ISP, '>HIHI', 0x0004, PC, 0x2014, PC)  # format 2 frame
    put(EXP + 0x1000 - 0x3aa, '>H', 0)  # the zero divisor
    return bytes(m)


def chunk(cid, data):
    return cid + struct.pack('>I', len(data)) + data + (b'\0' if len(data) & 1 else b'')


def iff(term, base, exp):
    head = struct.pack('>5I', 0x1000, 0, 3, 0x2014, 6) + b'file'.ljust(256, b'\0')
    head += struct.pack('>10I', 0, EXP, EXP, EXPLEN, 0x40000, 0x40000, 0x100, SLAVE, SLAVE, 0x40)
    head += b'Test.Slave'.ljust(256, b'\0')
    head += struct.pack('>5I5H2b', 17851, 687, 456, 0, 0, 0, 0x207, 20, 1, 7190, -1, -1)
    regs = [0, 0x17, 0x60000, 0x9480f0, 0xffff0000, 0, 9, 0x17, H1, EXP + 0x1000, 1, 2, 3, 4, 5]
    cpu = struct.pack('>19I', *regs, PC, SP, ISP, 0x19f800) + struct.pack('>HBB', 4, 5, 5)
    cpu += struct.pack('>11I', 0x9f0b40, 0, 0x2111, 0, 0, 0, 0, 0, 0, 0x22, 0)
    cpu += struct.pack('>QQQ3I', 0x100000000, 0x100000000, 0, 0, 0, 0) + bytes(96 + 12)
    cust = bytearray(0x400)
    for off, val, flag in ((0x02, 0x3d0, 1), (0x1c, 0x603c, 1), (0x96, 0x8200, 0x82),
                           (0x9a, 0, 2)):
        struct.pack_into('>H', cust, off, val)
        cust[0x200 + off] = cust[0x201 + off] = flag
    cia = struct.pack('>6B4H2I5B3x', 0, 0, 0xfe, 0xff, 3, 0, 0x21ff, 0x6b05, 0x21ff, 0xffff,
                      0x1aa, 0xffffff, 0x3f, 0, 0, 0, 1)
    body = b'WHDD' + chunk(b'HEAD', head) + chunk(b'TERM', term + b'\0') + \
        chunk(b'OPT ', b'Slave="Test.Slave" CoreDump\0') + chunk(b'CPU ', cpu) + \
        chunk(b'CUST', bytes(cust)) + chunk(b'CIAA', cia) + chunk(b'CIAB', cia) + \
        chunk(b'SLAV', b'\x70\xff\x4e\x75WHDLOADS'.ljust(0x40, b'\0')) + \
        chunk(b'MEM ', base) + chunk(b'EMEM', exp)
    return b'FORM' + struct.pack('>I', len(body)) + body


class WHDLDump(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        frame = f'${ISP:X} 0004{PC >> 16:04X} {PC & 0xffff:04X}2014 {PC:08X}'
        stack = f'${SP:X} 12345678 {H1 + 0x14:08X} {H1 + 0x1a:08X} {H1 + 0x16:08X}'
        old = report('15-Nov-26 10:00:00', PC + 0x100, frame, stack, 'Old.Slave')
        new = report('16-Nov-26 11:27:09', PC, frame, stack)
        self.write('.whdl_register', (old + new).encode('latin-1'))
        self.base = bytes(range(256)) * 16
        self.exp = expmem()
        self.term = (f'Exception "Integer Divide by Zero" ($2014)\nat ${PC:X} (Task '
                     f"'Initial CLI', ExpMem ${PC - EXP:X}) occurred.").encode()

    def write(self, name, data):
        with open(os.path.join(self.dir, name), 'wb') as f:
            f.write(data)

    def raw_files(self):
        self.write('.whdl_memory', self.base)
        self.write('.whdl_expmem', self.exp)

    def test_report_text(self):
        with open(os.path.join(self.dir, '.whdl_register'), encoding='latin-1') as f:
            reps = whdldump.split_reports(f.read())
        self.assertEqual(len(reps), 2)
        r = whdldump.parse_report(reps[-1])
        self.assertEqual(r['version'], '20.1.7190')
        self.assertEqual(r['slave'], {'name': 'Test.Slave', 'file_size': 1234})
        self.assertEqual(r['regions']['ExpMem']['start'], EXP)
        self.assertEqual(r['regions']['BaseMem']['size'], 0x1000)
        self.assertEqual(r['regions']['Resload']['GL'], 0x40200)
        t = r['termination']
        self.assertEqual(t['exception'], {'name': 'Integer Divide by Zero', 'code': 0x2014,
                                          'format': 2, 'offset': 0x14, 'vector': 5})
        self.assertEqual((t['address'], t['task']), (PC, 'Initial CLI'))
        self.assertEqual(t['region'], {'name': 'ExpMem', 'offset': PC - EXP})
        g = r['registers']
        self.assertEqual((g['d3'], g['a0'], g['a6'], g['pc'], g['sr'], g['isp'], g['crp']),
                         (0x9480f0, H1, 5, PC, 4, ISP, 0x100000000))
        self.assertEqual(r['frame']['address'], ISP)
        self.assertEqual(r['frame']['bytes'][:6], struct.pack('>HI', 4, PC))
        self.assertEqual(r['stack']['address'], SP)
        self.assertEqual(r['disassembly'][1], (PC, 'move.w d4,d5'))
        self.assertEqual((r['custom']['INTENAR'], r['custom']['DMACONR'], r['custom']['VHPOSR']),
                         (0x603c, 0x3d0, 0x275))
        self.assertEqual((r['ciaa']['crb'], r['ciaa']['prao'], r['ciaa']['tb_latch'],
                          r['ciab']['ddra'], r['ciab']['icr']), (1, 0xfe, 0xffff, 0xc0, 4))
        self.assertNotIn('\x9b', json.dumps(r, default=str))

    def test_report_selection(self):
        self.assertEqual(whdldump.Dump(self.dir).report['slave']['name'], 'Test.Slave')
        d = whdldump.Dump(self.dir, report=0)
        self.assertEqual(d.report['slave']['name'], 'Old.Slave')
        self.assertEqual(d.registers()['pc'], PC + 0x100)

    def test_memory_files_and_hunks(self):
        self.raw_files()
        d = whdldump.Dump(self.dir, hunk0=H0)
        self.assertEqual(d.read(0x10, 4), bytes([0x10, 0x11, 0x12, 0x13]))
        self.assertEqual(d.word(EXP + 0x1000 - 0x3aa), 0)
        self.assertEqual(d.long(SP), 0x12345678)
        self.assertRaises(KeyError, d.read, EXP + EXPLEN - 2, 4)
        self.assertEqual(d.where(PC), ('ExpMem', PC - EXP))
        self.assertEqual(d.where(SLAVE + 4), ('Slave', 4))
        self.assertEqual(d.hunks, [(H0, 0x300), (H1, 0x100)])
        self.assertEqual(d.hunk_of(PC), (1, 0x20))
        self.assertIsNone(d.hunk_of(H1 + 0x100))
        self.assertEqual(d.reg('a7'), SP)
        self.assertEqual(d.reg('sp'), SP)
        rets = d.return_addresses()
        self.assertEqual([(a, v) for a, v, ok in rets], [(SP + 4, H1 + 0x14), (SP + 8, H1 + 0x1a)])
        self.assertTrue(all(ok for _, _, ok in rets))
        self.assertEqual(whdldump.parse_addr('h1+$20', d), PC)
        self.assertEqual(whdldump.parse_addr('a1-0x3aa', d), EXP + 0x1000 - 0x3aa)
        f = d.frame()
        self.assertEqual((f['format'], f['vector'], f['pc'], f['address']), (2, 5, PC, PC))

    def test_segs_with_sizes_without_memory(self):
        d = whdldump.Dump(self.dir, segs=[(H0, 0x300), (H1, 0x100)])
        self.assertEqual(d.describe(PC), f'${PC:X} ExpMem+${PC - EXP:X} hunk 1 +$20')
        self.assertEqual([(a, v, ok) for a, v, ok in d.return_addresses()],
                         [(SP + 4, H1 + 0x14, False), (SP + 8, H1 + 0x1a, False),
                          (SP + 12, H1 + 0x16, False)])

    def test_binary_dump_only(self):
        os.unlink(os.path.join(self.dir, '.whdl_register'))
        self.write('.whdl_dump', iff(self.term, self.base, self.exp))
        d = whdldump.Dump(self.dir, segs=[H0, H1])
        self.assertEqual(d.head['version'], '20.1.7190')
        self.assertEqual(d.head['datestamp'], '16-Nov-26 11:27:09')
        self.assertEqual(d.cpu_name(), '68030')
        self.assertEqual(d.hunks, [(H0, 0x300), (H1, 0x100)])
        g = d.registers()
        self.assertEqual((g['pc'], g['a7'], g['isp'], g['tt0']), (PC, SP, ISP, 0))
        self.assertNotIn('pcr', g)  # a 68060 register: leftovers on a 68030
        self.assertEqual(d.read(SLAVE + 4, 8), b'WHDLOADS')
        self.assertEqual(d.long(PC - 4), 0x83c24e75)
        self.assertEqual(d.custom[0x1c], (0x603c, 1))
        self.assertEqual(d.custom[0x96], (0x8200, 0x82))
        self.assertNotIn(0x9a, d.custom)  # write-only, not modified
        self.assertEqual(d.ciaa['prao'], 0xfe)
        self.assertEqual(d.termination()['exception']['vector'], 5)
        s = d.summary()
        self.assertEqual((s['pc']['region'], s['pc']['offset'], s['pc']['hunk']), ('ExpMem', PC - EXP, 1))
        self.assertEqual(s['frame']['at'], ISP)
        self.assertEqual(s['custom']['INTENAR'], 0x603c)
        self.assertEqual(s['options'], 'Slave="Test.Slave" CoreDump')

    def test_older_report_keeps_its_registers(self):
        self.write('.whdl_dump', iff(self.term, self.base, self.exp))
        d = whdldump.Dump(self.dir, report=0)
        self.assertEqual(d.registers()['pc'], PC + 0x100)
        self.assertIsNone(d.custom)
        self.assertTrue(d.warnings)
        self.assertEqual(whdldump.Dump(self.dir).registers()['pc'], PC)

    def test_iff_rejects(self):
        self.assertRaises(ValueError, whdldump.parse_iff, b'FORM\0\0\0\4ILBM')
        self.assertRaises(ValueError, whdldump.parse_iff, b'FORM\0\0\0\x14WHDDHEAD\0\0\1\0')

    def test_cli(self):
        self.raw_files()
        out = io.StringIO()
        with redirect_stdout(out):
            whdldump.main([self.dir, '--seg', f'{H0:#x},{H1:#x}'])
        text = out.getvalue()
        self.assertIn('(report 2 of 2)', text)
        self.assertIn(f'PC ${PC:X} ExpMem+${PC - EXP:X} hunk 1 +$20', text)
        self.assertIn(f'(a trap: the stacked PC follows the trapping instruction, ${PC - 4:X}', text)
        self.assertIn(f'${SP + 4:08X}  ${H1 + 0x14:X} ExpMem+${H1 + 0x14 - EXP:X} hunk 1 +$14', text)
        self.assertIn(f'> ${PC:08X} h1+00020', text)
        out = io.StringIO()
        with redirect_stdout(out):
            whdldump.main([self.dir, 'read', 'h1+$20', '4', '--hunk0', hex(H0)])
        self.assertTrue(out.getvalue().startswith(f'${PC:08X}  3A044E75'))
        out = io.StringIO()
        with redirect_stdout(out):
            whdldump.main(['--json', self.dir])
        self.assertEqual(json.loads(out.getvalue())['pc']['offset'], PC - EXP)
        out = io.StringIO()
        with redirect_stdout(out):
            whdldump.main([self.dir, 'reports'])
        self.assertEqual(len(out.getvalue().splitlines()), 2)

    @unittest.skipUnless(os.path.exists(tool('objdump')), 'no m68k objdump')
    def test_dis(self):
        self.raw_files()
        d = whdldump.Dump(self.dir)
        lines = d.disassemble(PC - 4, 8).splitlines()
        self.assertRegex(lines[0], r'^\s*%x:\s+83c2\s+divs\.w d2,d1$' % (PC - 4))
        self.assertRegex(lines[2], r'^\s*%x:\s+3a04\s+move\.w d4,d5$' % PC)

    @unittest.skipUnless(os.environ.get('WHDLDUMP_SAMPLE'), 'WHDLDUMP_SAMPLE not set')
    def test_sample(self):
        r = subprocess.run([sys.executable, '-m', 'amigaxdev.whdldump', '--json',
                            os.environ['WHDLDUMP_SAMPLE']], capture_output=True, text=True,
                           cwd=PYLIB, check=True)
        s = json.loads(r.stdout)
        self.assertIn('pc', s)
        self.assertTrue(s['registers'])


if __name__ == '__main__':
    unittest.main()
