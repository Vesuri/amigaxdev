#!/usr/bin/env python3
"""Authored 68040 physical-memory/cache observer matrix; no game bytes required.

Source the shared environment first. --work-dir must be a fresh ignored directory.
The cached view is physical, not an MMU logical translation. The fixture uses
identity-mapped WHDLoad ExpMem and uncached BaseMem; other mappings are out of scope.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(base, mmu, cache, baseline=False):
    log = (base/'gdb.log').read_text()
    phases = re.findall(r'^OBS ([12]) d2=([0-9a-f]+) d3=([0-9a-f]+) cacr=([0-9a-f]+) tc=([0-9a-f]+) marker=([0-9a-f]+)$', log, re.M)
    assert len(phases) == 2, 'OBS / TWO POSITIVE PHASES'
    expected = bytearray(range(0x40, 0xa0))
    for phase, row in enumerate(phases, 1):
        n, d2, d3, cacr, tc, marker = (int(x,16)&0xffffffff for x in row)
        value = 0x13579bdf if phase == 1 else 0x89abcdef
        assert (n,d2,d3,marker)==(phase,value,0x2468ace0,0x4f425330+phase), 'OBS / CPU VALUES'
        assert cacr & 0x80008000 == (0x80008000 if cache else 0), 'OBS / CACHE STATE'
        assert tc == (0x8000 if mmu else 0), 'OBS / TRANSLATION STATE'
        expected[:4] = value.to_bytes(4,'big')
        expected[4:8] = bytes.fromhex('2468ace0')
        expected[15:19] = bytes.fromhex('11223344')
        raw = (base/f'raw{phase}.bin').read_bytes()
        assert len(raw)==96, 'OBS / RAW EXTENT'
        if baseline:
            if cache and mmu: assert raw != expected, 'OBS / BASELINE MUST REPRODUCE STALE READ'
            elif not cache: assert raw == expected, 'OBS / UNCACHED CONTROL'
        else:
            assert (base/f'cache{phase}.bin').read_bytes()==expected, 'OBS / COHERENT DATA'
            assert (base/f'raw-after{phase}.bin').read_bytes()==raw, 'OBS / NO WRITEBACK'
            if cache and mmu: assert raw != expected, 'OBS / DIRTY LINE CONTROL'
            elif not cache: assert raw == expected, 'OBS / UNCACHED CONTROL'
        assert (base/f'chip{phase}.bin').read_bytes()==bytes.fromhex('10203040'), 'OBS / UNCACHED CHIP'
    config=(base/'logs/debug.uae').read_text().splitlines()
    for setting in ('cpu_model=68040','mmu_model=68040','cachesize=0','cpu_compatible=true','cpu_data_cache=true'):
        assert setting in config, 'OBS / EFFECTIVE '+setting
    assert 'OBS COMPLETE' in log, 'OBS / NATIVE COMPLETION'
    assert (base/'done.bin').read_bytes()==b'PASS', 'OBS / CPU CONTINUATION'
    assert (base/'boot/returned').exists(), 'OBS / SHELL RETURN'
    assert (base/'boot/passed').exists() and not (base/'boot/failed').exists(), 'OBS / SHELL SUCCESS'
    report=(base/'boot/.whdl_register').read_text(encoding='latin1')
    assert report.count('\nReturn OK.\n')==1, 'OBS / NORMAL EXIT'
    return {'mmu':mmu,'cache':cache,'baseline':baseline,'result':'PASS'}


def controls(base, mmu, cache):
    cases=[('cache1.bin',lambda b:bytes([b[0]^1])+b[1:]),
           ('cache2.bin',lambda b:b[16:]+b[:16]),
           ('raw-after1.bin',lambda b:bytes([b[0]^1])+b[1:]),
           ('chip1.bin',lambda b:b'\0'*4),
           ('done.bin',lambda b:b'FAIL'),
           ('gdb.log',lambda b:b.replace(b'OBS 2 ',b'LOST 2 ')),
           ('gdb.log',lambda b:b.replace(b'd2=13579bdf',b'd2=13579bde')),
           ('logs/debug.uae',lambda b:b.replace(b'cpu_data_cache=true',b'cpu_data_cache=false'))]
    for name, damage in cases:
        p=base/name; original=p.read_bytes(); changed=damage(original)
        assert changed!=original, 'OBS / CONTROL TARGET'
        try:
            p.write_bytes(changed)
            try: check(base,mmu,cache)
            except AssertionError: pass
            else: raise AssertionError('OBS / ACCEPTED CORRUPTION '+name)
        finally: p.write_bytes(original)
    return len(cases)


def run(base, emulator, mmu, cache, baseline):
    for folder in ('boot/s','state','home'): (base/folder).mkdir(parents=True)
    env=dict(os.environ)
    for name, source in [('WHDLoad',env['WHDLOAD_BINARY']),('Observer.slave',base.parent/('Observer-cache.slave' if cache else 'Observer.slave'))]:
        shutil.copyfile(source,base/'boot'/name)
    opts=('MMU ' if mmu else 'NOMMU ')+('' if cache else 'NOCACHE ')
    (base/'boot/s/WHDLoad.prefs').write_text('Expert\nReadDelay=0\n')
    (base/'boot/s/startup-sequence').write_text('FailAt 999\nDH0:WHDLoad DH0:Observer.slave '+opts+'NOREQ SPLASHDELAY=0 COREDUMP >DH0:result\nIf WARN\nEcho failed >DH0:failed\nElse\nEcho passed >DH0:passed\nEndIf\nEcho returned >DH0:returned\n')
    launch=base/'launch.sh'
    launch.write_text('''#!/bin/bash
set -euo pipefail
cd "$1"
FSUAE_RUN=.
. "$FSUAE_COMMON"
trap 'fsuae_stop' EXIT
FSUAE="$2"
AMIGA_SETUP=a1200-040 DEBUG=1 SOUND=0 WINDOW=none WARP=1 NTSC=0
fsuae_options
echo "$DEBUG_PORT" > debug-port
fsuae_launch --hard_drive_0="$PWD/boot" --hard_drive_0_priority=10 --floppy_drive_0="$WORKBENCH_ADF" --floppy_drive_volume=0 --floppy_drive_volume_empty=0 --state_dir="$PWD/state" --logs_dir="$PWD/logs"
wait "$FSUAE_PID"
''')
    with (base/'launch.log').open('w') as log:
        process=subprocess.Popen(['/bin/bash',str(launch),str(base),str(emulator)],stdout=log,stderr=log)
        try:
            for _ in range(100):
                if (base/'debug-port').exists():
                    port=(base/'debug-port').read_text().strip()
                    if subprocess.run(['lsof','-nP','-iTCP:'+port,'-sTCP:LISTEN'],capture_output=True).returncode==0: break
                time.sleep(.2)
            else: raise AssertionError('OBS / LISTENER')
            script='set pagination off\nset confirm off\nset remotetimeout 120\nset stack-cache off\nset code-cache off\n'
            script+=f'target remote 127.0.0.1:{port}\nmonitor fields 600\nmaintenance flush register-cache\n'
            for phase in (1,2):
                script+=f'if $d6 != {0x4f425330+phase:#x}\nquit 1\nend\n'
                script+=f'printf "OBS {phase} d2=%lx d3=%lx cacr=%lx tc=%lx marker=%lx\\n",$d2,$d3,$d4,$d5,$d6\n'
                script+=f'dump binary memory raw{phase}.bin $a3 $a3+96\n'
                if not baseline:
                    script+='monitor memory cache\n'
                    script+=f'dump binary memory cache{phase}.bin $a3 $a3+96\nmonitor memory physical\ndump binary memory raw-after{phase}.bin $a3 $a3+96\n'
                script+=f'dump binary memory chip{phase}.bin 0x400 0x404\nset $next=$a4\nbreak *$next\ncontinue\nif $pc != $next\nquit 1\nend\ndelete breakpoints\n'
                if phase==1: script+='stepi 4\n'
            script+='break *$a5\ncontinue\nif $pc != $a5\nquit 1\nend\ndump binary memory done.bin 0x404 0x408\nprintf "OBS COMPLETE\\n"\ndelete breakpoints\nmonitor fields 200\ndetach\nquit\n'
            (base/'observe.gdb').write_text(script)
            with (base/'gdb.log').open('w') as out:
                subprocess.run(['m68k-amiga-elf-gdb','--batch','-q','-x','observe.gdb'],cwd=base,env=dict(env,HOME=str(base/'home'),XDG_CACHE_HOME=str(base/'home')),stdout=out,stderr=out,timeout=180,check=True)
            for _ in range(50):
                if (base/'boot/returned').exists():break
                time.sleep(.1)
        finally:
            subprocess.run(['/bin/bash','-c','FSUAE_RUN="$1"; . "$FSUAE_COMMON"; fsuae_stop_previous','stop',str(base)],check=True)
            process.wait(timeout=10)
    result=check(base,mmu,cache,baseline)
    if not baseline: result['rejection_controls']=controls(base,mmu,cache)
    (base/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(base.name,json.dumps(result),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--input-pins',type=Path,required=True,help='JSON mapping environment roots/relative paths (or GDB) to SHA-256')
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--repeats',type=int,default=2)
    args=parser.parse_args()
    if not 1 <= args.repeats <= 10:parser.error('--repeats must be between 1 and 10')
    assert sha(args.emulator)==args.sha256, 'OBS / EMULATOR PIN'
    required={'VASM','WHDLOAD_BINARY','KICKSTART_A1200','WORKBENCH_ADF','FSUAE_COMMON','GDB','WHDLOAD/Include/whdload.i'}
    pins=json.loads(args.input_pins.read_text())
    assert required <= pins.keys(), 'OBS / INCOMPLETE INPUT PINS'
    for key,digest in pins.items():
        root,_,suffix=key.partition('/')
        path=Path(shutil.which('m68k-amiga-elf-gdb')) if root=='GDB' else Path(os.environ[root])
        if suffix:path=path/suffix
        assert sha(path)==digest, 'OBS / INPUT PIN '+key

    base=args.work_dir.resolve();base.mkdir(parents=True,exist_ok=False)
    source=REPO/'share/fixtures/CacheObserver.s'
    for cache in (False,True):
        subprocess.run([os.environ['VASM'],'-m68040','-no-opt','-Fhunkexe']+(['-DOBS_CACHE=1'] if cache else [])+['-I'+os.environ['WHDLOAD']+'/Include','-I'+os.environ['NDK'],'-o',str(base/('Observer-cache.slave' if cache else 'Observer.slave')),str(source)],check=True)
    (base/'inputs.json').write_text(json.dumps({str(p):sha(p) for p in [source,args.emulator,Path(os.environ['WHDLOAD_BINARY']),Path(os.environ['KICKSTART_A1200']),Path(os.environ['WORKBENCH_ADF']),Path(os.environ['FSUAE_COMMON']),Path(os.environ['VASM'])]},indent=2)+'\n')
    for repeat in range(1,args.repeats+1):
        for mmu,cache in ((True,True),(True,False),(False,True),(False,False)):
            run(base/f'{repeat}-mmu{int(mmu)}-cache{int(cache)}',args.emulator.resolve(),mmu,cache,args.baseline)
    reports=[json.loads(p.read_text()) for p in sorted(base.glob('*/result.json'))]
    assert len(reports)==4*args.repeats, 'OBS / COMPLETE MATRIX'
    (base/'matrix.json').write_text(json.dumps(reports,indent=2)+'\n')
    print('OBSERVER MATRIX PASS:',len(reports),flush=True)

if __name__=='__main__':main()
