#!/usr/bin/env python3
"""Compare debugger SR packets with CPU-saved CCR in an authored fixture."""
import argparse, json, os, re, shutil, subprocess, time
from pathlib import Path
from test_cache_observer import sha, REPO
EXPECTED=(4,8,0,20,24,16,25,10,2,21)


def check(base, baseline=False):
    log=(base/'gdb.log').read_text()
    cpu=re.findall(r'^CCR (\d+) cpu=([0-9a-f]+)$',log,re.M)
    dbg=re.findall(r'^CCR (\d+) debugger=([0-9a-f]+)$',log,re.M)
    raw=re.findall(r'received: "([0-9a-f]{8})"',log)
    assert [int(i) for i,v in cpu]==list(range(10)), 'CCR / CPU COVERAGE'
    assert [int(i) for i,v in dbg]==list(range(10)) and len(raw)==10, 'CCR / DEBUGGER COVERAGE'
    assert tuple(int(v,16)&31 for i,v in cpu)==EXPECTED, 'CCR / CPU FLAGS'
    observed=tuple(int(v,16)&31 for i,v in dbg)
    assert observed==tuple(int(v,16)&31 for v in raw), 'CCR / PACKET AGREEMENT'
    if baseline: assert observed!=EXPECTED, 'CCR / STALE BASELINE CONTROL'
    else: assert observed==EXPECTED, 'CCR / CURRENT FLAGS'
    assert 'CCR COMPLETE\n' in log and (base/'done.bin').read_bytes()==b'PASS', 'CCR / COMPLETION'
    assert (base/'boot/returned').exists() and (base/'boot/passed').exists() and not (base/'boot/failed').exists(), 'CCR / RETURN'
    assert (base/'boot/.whdl_register').read_text(encoding='latin1').count('\nReturn OK.\n')==1, 'CCR / NORMAL EXIT'
    return observed


def run(base, emulator, setup, baseline):
    for folder in ('boot/s','state','home'): (base/folder).mkdir(parents=True)
    env=dict(os.environ)
    shutil.copyfile(env['WHDLOAD_BINARY'],base/'boot/WHDLoad')
    shutil.copyfile(base.parent/'Observer.slave',base/'boot/Observer.slave')
    (base/'boot/s/WHDLoad.prefs').write_text('Expert\nReadDelay=0\n')
    (base/'boot/s/startup-sequence').write_text('FailAt 999\nDH0:WHDLoad DH0:Observer.slave NOMMU NOCACHE NOREQ SPLASHDELAY=0 COREDUMP >DH0:result\nIf WARN\nEcho failed >DH0:failed\nElse\nEcho passed >DH0:passed\nEndIf\nEcho returned >DH0:returned\n')
    launch=base/'launch.sh'
    launch.write_text('''#!/bin/bash
set -euo pipefail
cd "$1"
FSUAE_RUN=.
. "$FSUAE_COMMON"
trap 'fsuae_stop' EXIT
FSUAE="$2"
AMIGA_SETUP="$3" DEBUG=1 SOUND=0 WINDOW=none WARP=1 NTSC=0
fsuae_options
echo "$DEBUG_PORT" > debug-port
fsuae_launch --hard_drive_0="$PWD/boot" --hard_drive_0_priority=10 --floppy_drive_0="$WORKBENCH_ADF" --floppy_drive_volume=0 --floppy_drive_volume_empty=0 --state_dir="$PWD/state" --logs_dir="$PWD/logs"
wait "$FSUAE_PID"
''')
    with (base/'launch.log').open('w') as log:
        process=subprocess.Popen(['/bin/bash',str(launch),str(base),str(emulator),setup],stdout=log,stderr=log)
        try:
            for _ in range(100):
                if (base/'debug-port').exists():
                    port=(base/'debug-port').read_text().strip()
                    if subprocess.run(['lsof','-nP','-iTCP:'+port,'-sTCP:LISTEN'],capture_output=True).returncode==0: break
                time.sleep(.2)
            else: raise AssertionError('OBS / LISTENER')
            script='set pagination off\nset confirm off\nset remotetimeout 120\n'
            script+=f'target remote 127.0.0.1:{port}\nmonitor fields 600\nmaintenance flush register-cache\n'
            script+='if $d6 != 0x43435231\nquit 1\nend\nset $table=$a3\n'
            for i in range(len(EXPECTED)):
                script+=f'set $point=$table+*(short*)($table+{i*2})\nbreak *$point\ncontinue\nif $pc != $point\nquit 1\nend\ndelete breakpoints\n'
                script+=f'printf "CCR {i} debugger=%lx\\n",$sr\nmaintenance packet p10\nstepi\nprintf "CCR {i} cpu=%lx\\n",$d0\n'
            script+='break *$a5\ncontinue\nif $pc != $a5\nquit 1\nend\ndump binary memory done.bin 0x404 0x408\nprintf "CCR COMPLETE\\n"\ndelete breakpoints\nmonitor fields 200\ndetach\nquit\n'
            (base/'observe.gdb').write_text(script)
            with (base/'gdb.log').open('w') as out:
                subprocess.run(['m68k-amiga-elf-gdb','--batch','-q','-x','observe.gdb'],cwd=base,env=dict(env,HOME=str(base/'home'),XDG_CACHE_HOME=str(base/'home')),stdout=out,stderr=out,timeout=180,check=True)
            for _ in range(50):
                if (base/'boot/returned').exists():break
                time.sleep(.1)
        finally:
            subprocess.run(['/bin/bash','-c','FSUAE_RUN="$1"; . "$FSUAE_COMMON"; fsuae_stop_previous','stop',str(base)],check=True)
            process.wait(timeout=10)
    observed=check(base,baseline)
    if not baseline:
        for filename,damage in [('done.bin',lambda b:b'FAIL'),('gdb.log',lambda b:b.replace(b'CCR 0 cpu=',b'LOST 0 cpu=',1)),('gdb.log',lambda b:b.replace(b'CCR COMPLETE',b'INCOMPLETE',1))]:
            p=base/filename; original=p.read_bytes()
            try:
                p.write_bytes(damage(original))
                try:check(base)
                except AssertionError:pass
                else:raise AssertionError('CCR / ACCEPTED CORRUPTION')
            finally:p.write_bytes(original)
    print(base.name,'PASS baseline='+str(baseline),'observed='+str(observed),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator',type=Path,required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--input-pins',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--baseline',action='store_true');a=p.parse_args()
    assert sha(a.emulator)==a.sha256, 'CCR / EMULATOR PIN'
    pins=json.loads(a.input_pins.read_text())
    assert {'VASM','WHDLOAD_BINARY','KICKSTART_A1200','WORKBENCH_ADF','FSUAE_COMMON','GDB','WHDLOAD/Include/whdload.i'} <= pins.keys()
    for key,digest in pins.items():
        root,_,suffix=key.partition('/')
        path=Path(shutil.which('m68k-amiga-elf-gdb')) if root=='GDB' else Path(os.environ[root])
        assert sha(path/suffix if suffix else path)==digest, 'CCR / INPUT PIN '+key
    base=a.work_dir.resolve();base.mkdir(parents=True,exist_ok=False)
    source=REPO/'share/fixtures/RegisterObserver.s'
    subprocess.run([os.environ['VASM'],'-m68020','-no-opt','-Fhunkexe','-I'+os.environ['WHDLOAD']+'/Include','-I'+os.environ['NDK'],'-o',str(base/'Observer.slave'),str(source)],check=True)
    for repeat in (1,2):
        for setup in ('a1200-030','a1200-040'):
            run(base/f'{repeat}-{setup}',a.emulator.resolve(),setup,a.baseline)
    print('CCR MATRIX PASS: two repeats on 030 and 040')

if __name__=='__main__':main()
