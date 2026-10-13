# The shared environment

`make setup` installs one environment under `~/.local`; every project takes its tools and
shared files from there, through the variables below. Nothing in a project repo names a path
on a particular machine (playbook §0).

## Using it from a project

A project's `amiga/env.sh` sources the shared file, then adds only what is its own:

```sh
#!/usr/bin/env bash
# Project values that differ from the shared defaults go *before* the source line:
#   export WHDLOAD="${WHDLOAD:-$HOME/.local/share/amiga/WHDLoad}"   # e.g. a 19.2 build
. "${AMIGA_ENV:-$HOME/.local/share/amiga/env.sh}"
```

The shared `env.sh` keeps every value that is already set, so a caller's environment beats a
project's choice, which beats the shared default. Run scripts source `amiga/env.sh` and then
`"$FSUAE_COMMON"`. Python tools read the same variables, with the same defaults:

```python
TOOLCHAIN = os.environ.get('AMIGA_TOOLCHAIN', os.path.expanduser('~/.local/opt'))
OBJDUMP = os.path.join(TOOLCHAIN, 'bin', 'm68k-amiga-elf-objdump')
```

or, simpler, through the shared `amigaxdev` package (`from amigaxdev.env import path, tool`).
The shared venv has it on its path already; a tool that may run under another `python3` puts
this shim (`tools/_amigaxdev.py`) next to itself and imports it first:

```python
# Find AmigaXDev's shared Python package (amigaxdev) under any python3.
import os, sys
sys.path.insert(0, os.environ.get('AMIGA_PYLIB') or os.path.expanduser('~/.local/share/amiga/pylib'))
```

Makefiles use `?=` with the same default, so they work with or without `env.sh`.

## Variables

| Variable | Default | What |
|---|---|---|
| `AMIGA_PREFIX` | `~/.local` | where setup installed (`make setup PREFIX=`) |
| `AMIGA_SHARE` | `$AMIGA_PREFIX/share/amiga` | the shared tree |
| `AMIGA_TOOLCHAIN` | `$AMIGA_PREFIX/opt` | m68k-amiga-elf gcc, gdb, objdump (`bin/`) and NDK headers |
| `VASM` | `$AMIGA_PREFIX/vasmm68k_mot` | vasm, Motorola syntax (x86_64) |
| `NDK` | `$AMIGA_TOOLCHAIN/m68k-amiga-elf/sys-include` | NDK includes for vasm (`lvo/*_lib.i`, `exec/*.i`) |
| `FSUAE_ARM` | `$AMIGA_SHARE/fs-uae-arm/fs-uae` | native arm64 FS-UAE with the gdb stub |
| `FSUAE_APROF` | `fs-uae-aprof/fs-uae` | the same with the exact-cycle profiler: `monitor aprof start` / `monitor aprof stop FILE` |
| `AMIGA_UNICORN` | `unicorn` | Unicorn 2.1.4 with QEMU's fix for constant subtract-with-borrow on arm64 (`lib/libunicorn.2.dylib`, `include/`); Homebrew's 2.1.4 dies there with SIGILL. Opt-in: a Makefile can take `UNICORN_PREFIX ?= $(AMIGA_UNICORN)`, a ctypes binding `$AMIGA_UNICORN/lib/libunicorn.2.dylib` |
| `KICKSTART` | `Kickstarts/kick40063.A600` | host ROM: Kickstart 3.1 r40.063 |
| `KICKSTART_A1200` | `Kickstarts/kick40068.A1200` | 68020 host ROM: Kickstart 3.1 r40.068 |
| `KICK13`, `KICKSTART13` | `Kickstarts/kick34005.A500` | Kickstart 1.3 for KickEmu `kick13` slaves (two names, same file) |
| `RTB` | `$KICK13.RTB` | its relocation table |
| `WORKBENCH_ADF` | `Workbenchv2.04rev37.67Workbench.adf` | Workbench 2.04 boot floppy (`C:` and `Libs:`) |
| `SETPATCH` | `SetPatch` | SetPatch 40.16 from Workbench 3.1 |
| `WHDLOAD` | `WHDLoad-20.0` | WHDLoad 20.0: `Include/`, `Src/sources/whdload/` (KickEmu), `C/WHDLoad` |
| `WHDLOAD_BINARY` | `$WHDLOAD/C/WHDLoad` | the WHDLoad executable put on the game drive |
| `INSTALLER43` | `Installer43/Installer` | Commodore Installer 43.3 |
| `ADCD` | `adcd21/Reference` | Developer CD 2.1 `Reference/`: `ROM_Kernel_Manuals/Hardware_Manual` (and `Libraries_Manual`, `Devices_Manual`, AmigaGuide text), `HTML/` (the same as pages), autodocs, Amiga Mail |
| `AGA_GUIDE` | `AGA.Guide` | AGA chipset registers (the Hardware Reference Manual covers OCS/ECS) |
| `FSUAE_COMMON` | `fsuae_common.sh` | pid-scoped emulator handling, a gdb-stub port per directory |
| `LHA` | `lha-compressor/src/lha` | LHa for UNIX, which creates release archives |
| `AMIGA_PYLIB` | `pylib` | the `amigaxdev` Python package (below) |
| `AMIGA_GHIDRA_SCRIPTS` | `ghidra_scripts` | shared Ghidra scripts: `-scriptPath "ghidra_scripts;$AMIGA_GHIDRA_SCRIPTS"` |
| `AMIGA_FRAMEWORK` | `framework` | the canonical dA JoRMaS framework the ports compare their copies with |

Paths without a directory are under `$AMIGA_SHARE`. The shared `env.sh` also puts
`$AMIGA_SHARE/python/bin`, `$AMIGA_TOOLCHAIN/bin`, `$AMIGA_PREFIX` and
`$AMIGA_PREFIX/fs-uae` on `PATH`, in that order, so `python3`, `m68k-amiga-elf-gdb`,
`vasmm68k_mot` and `fs-uae` (the x86_64 one) resolve to the shared copies.

Other shared files have no variable of their own:

| File | What |
|---|---|
| `Kickstarts/kick33180.A500`, `kick37175.A500` (+ `.RTB`) | Kickstart 1.2 and 2.04 (A500+), for testing slaves on them |
| `WHDLoad/` | WHDLoad 19.2, to test that a slave still runs on older versions |
| `ndk/` | NDK 3.2 Release 4 (`Include_I/`, `Include_H/`, Autodocs) |
| `kalms-c2p/` | Mikael Kalms' c2p routines; vendor the ones used (playbook §10) |
| `python/` | Python 3.12 with Pillow, numpy, capstone and amitools (`xdftool` reads and writes ADFs) |
| `new-game-playbook*.md` | the playbooks, from `docs/playbooks/` |

## Shared tools

Run scripts using the shared launcher accept `AMIGA_SETUP` to select a complete machine,
for example `AMIGA_SETUP=a1200-fast amiga/run.sh`. Available names are `a500`, `a500+`,
`a1200`, `a1200-fast`, `a1200-030`, `a1200-040` and `a1200-060`. The preset overrides
project machine defaults at launch; `EXTRA_ARGS` remains the explicit override. See
[named machine setups](reference/headless-fsuae.md#named-machine-setups) for RAM, ROMs,
clocks, MMU settings and project compatibility limits. CPU cache emulation is enabled
for 68020 and faster (instruction cache on 020; instruction and data caches on 030+).
Guest software still controls cache use. Install updates with `make share`.

On macOS the shared launcher defaults debug/diagnostic runs to the leftmost display when
multiple monitors are connected; ordinary interactive runs keep their usual placement.
`AMIGA_MONITOR=left|right|primary` selects a display explicitly for either kind of run;
`AMIGA_MONITOR=` disables automatic positioning. See
[window placement](reference/headless-fsuae.md#sound-window-screenshots).

| What | Use | Replaces the per-project |
|---|---|---|
| `amigaxdev.env` | `path(NAME)`, `tool('objdump')`: the shared defaults with environment overrides | `local_env.py`, inline `AMIGA_TOOLCHAIN` lookups |
| `amigaxdev.barto` | `load(trace)`, `Trace.instructions(field)`, `capture_part_starts()`; honours `NAME.pc-base` | `barto.py` |
| `amigaxdev.gdbserve` | `Server(name, root, commands={...}).main(argv)`: serve / one-shot commands through the gdb stub (`stop`, `cont`, `gdb`, `shot`, `profile`, `wait`, `until`, `quit`; `commands` add or replace) | the `td2.py` skeleton |
| `amigaxdev.disasm` | `python3 -m amigaxdev.disasm dis\|disd\|hotspots [--label NAME] ...` | `dis.sh`, `disd.py`, `hotspots.py` |
| `amigaxdev.adf`, `amigaxdev.patchlist` | `python3 -m amigaxdev.adf DISK`, `python3 -m amigaxdev.patchlist SLAVE OFFSET` | `adf.py`, `patchlist.py` |
| `amigaxdev.release` | `archive(prefix, files, drawer_icon, dos_stamp(y, m, d))`, `write()`, `refuse_originals()`, `installer_icon(icons_dir, appname)` | the body of `package_release.py`, `installer_icon.py` |
| `amigaxdev.mac` | `macbin`, `resource_fork`, `hfs_extract`, `gen_trap_names`, `m68k_sweep` | the Macintosh ports' copies |
| `amigaxdev.dos` | `mz_info` (with Compack detection), `verify_amiga_runtime` | the DOS ports' copies |
| `amigaxdev.framework` | `python3 -m amigaxdev.framework diff\|sync PROJECT`: the port's framework against `$AMIGA_FRAMEWORK` | — |
| Ghidra scripts | `DumpCallGraph`, `ExportListing`, `ExportAuditListing`, `DumpZeroPage`, `MacMarkEntries`, `MacApplyNames`, `MacDumpTraps` (Ghidra started from the project root: they read `ghidra_scripts/entrypoints.csv` and `tmp/trap_names.lua` there) | the identical per-port copies |
| `whdload/SmokeSlave.s` | assemble with `-I.` and a project `smoke_name.i` holding the name line | `whdload/SmokeSlave.s` |
| `fsuae_prepare`, `FSUAE_CLAIM_STRICT=1` | in `fsuae_common.sh`: claim for DEBUG=1 else stop the previous run; a strict claim that never takes a busy port | the `run.sh` claim block, Alone in the Dark's override |

Project-specific names (`KICKSTART_RTB`, `WHDLOAD_HOST_KICKSTART`, `FSUAE`, `GDB`, ...) stay
in the projects, defined from these. `FSUAE` is deliberately not shared: most run scripts use
the x86_64 `fs-uae` on `PATH`, because host lldb can attach to it (playbook §5).

## The ROMs

| File | TOSEC name |
|---|---|
| `kick33180.A500` | Kickstart v1.2 r33.180 (1986-10)(Commodore)(A500-A1000-A2000)[!] |
| `kick34005.A500` | Kickstart v1.3 r34.005 (1987-12)(Commodore)(A500-A1000-A2000-CDTV)[!] |
| `kick37175.A500` | Kickstart v2.04 r37.175 (1991-05)(Commodore)(A500+)[!] |
| `kick40063.A600` | Kickstart v3.1 r40.063 (1993-07)(Commodore)(A500-A600-A2000)[!] |
| `kick40068.A1200` | Kickstart v3.1 r40.068 (1993-12)(Commodore)(A1200)[!] |

All are the verified (`[!]`) dumps, the ones skick346's relocation tables are made for.

## Shared Macintosh runtime sources

`$AMIGA_SHARE/mac-runtime` holds the canonical C++ rectangle helpers used by
Alone in the Dark and Prince of Persia 2. Consumers vendor identical source files
and verify `manifest/shared-runtime.sha256` before compilation and host checks.
See `share/mac-runtime/README.md` for the update workflow. Game-specific trap ABI
and memory ownership checks remain in each port.
