# The shared environment

`make setup` installs one environment under `~/.local`; every project takes its tools and
shared files from there, through the variables below. Nothing in a project repo names a path
on a particular machine (playbook §0).

For task-specific guidance, use the [task index](index.md). This page is a lookup
for integration and variables, not a prerequisite for every project task.

## Using it from a project

A project's `amiga/env.sh` sources the shared file, then adds only what is its own:

```sh
#!/usr/bin/env bash
# Project values that differ from the shared defaults go *before* the source line:
#   export WHDLOAD="${WHDLOAD:-$HOME/.local/share/amiga/WHDLoad}"   # optional explicit shared tree
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
The shared venv has it on its path already (`amiga/env.sh` puts that venv's `python3` first,
so run tools after sourcing it; a bare shell may find another `python3`, where
`python3 -m amigaxdev...` fails); a tool that may run under another `python3` puts
this shim (`tools/_amigaxdev.py`) next to itself and imports it first:

```python
# Find AmigaXDev's shared Python package (amigaxdev) under any python3.
import os, sys
sys.path.insert(0, os.environ.get('AMIGA_PYLIB') or os.path.expanduser('~/.local/share/amiga/pylib'))
```

Makefiles use `?=` with the same default, so they work with or without `env.sh`.

## A project's agent instructions

Every project gives its agents the same way into the shared environment: an `AGENTS.md` at the
root, and no `CLAUDE.md`. Claude Code (2.1.277 and later) reads `AGENTS.md` when no `CLAUDE.md`
exists in the working directory or above it, and other agents read it anyway. A project that
already has a `CLAUDE.md` holding `@AGENTS.md` works too; leave it. A fork worktree keeps
`AGENTS.md` untracked, in the repository's local exclude file (the
[JOTD](playbooks/new-game-playbook-jotd.md) and [StingRay](playbooks/new-game-playbook-stingray.md)
playbooks). `AGENTS.md` holds rules and pointers only, because agents reread it on every turn:

1. The personal commit rules, then the selected playbook's §0 rules.
2. The scope and where to start: `docs/open-work.md` (a fork: its harness notes) is read first.
3. A table of the project's own docs, each with when to read it.
4. The way into the shared knowledge, as one installed path, for example:

   > Shared guidance starts at `~/.local/share/amiga/docs/index.md`: read the rows that match
   > the task. It routes to the playbooks, references and shared tools (`docs/environment.md`,
   > "Shared tools"); this project follows `docs/playbooks/new-game-playbook.md` there. The
   > environment comes from AmigaXDev's `make setup`, and `amiga/env.sh` sources
   > `~/.local/share/amiga/env.sh`. Generic lessons go into AmigaXDev's docs (edit them there and
   > run `make share`); this repository keeps what is specific to this game.

`make share` installs `docs/` at `~/.local/share/amiga/docs/`, so the path works from any
checkout or worktree, its links resolve, and it describes the installed tools. Point at the index
instead of copying it or listing its documents: a copy goes stale with the next fix here. The
tools come the same way: `amiga/env.sh` sources the shared `env.sh`, run scripts launch through
`$FSUAE_COMMON`, and Python tools import `amigaxdev`, so a project gets `make share` updates
without edits.

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
| `WHDLOAD` | `WHDLoad` | WHDLoad 20.1: `Include/`, `Src/sources/whdload/` (KickEmu), `C/WHDLoad` |
| `WHDLOAD_BINARY` | `$WHDLOAD/C/WHDLoad` | the WHDLoad executable put on the game drive |
| `INSTALLER43` | `Installer43/Installer` | Commodore Installer 43.3 |
| `ADCD` | `adcd21/Reference` | Developer CD 2.1 `Reference/`: `ROM_Kernel_Manuals/Hardware_Manual` (and `Libraries_Manual`, `Devices_Manual`, AmigaGuide text), `HTML/` (the same as pages), autodocs, Amiga Mail |
| `AGA_GUIDE` | `AGA.Guide` | AGA chipset registers (the Hardware Reference Manual covers OCS/ECS) |
| `FSUAE_COMMON` | `fsuae_common.sh` | pid-scoped emulator handling, a gdb-stub port per directory |
| `LHA` | `lha-compressor/src/lha` | LHa for UNIX, which creates release archives |
| `AMIGA_PYLIB` | `pylib` | the `amigaxdev` Python package (below) |
| `AMIGA_GHIDRA_SCRIPTS` | `ghidra_scripts` | shared Ghidra scripts: `-scriptPath "ghidra_scripts;$AMIGA_GHIDRA_SCRIPTS"` |
| `AMIGA_FRAMEWORK` | `framework` | the canonical framework the ports compare their copies with |

Paths without a directory are under `$AMIGA_SHARE`. The shared `env.sh` also puts
`$AMIGA_SHARE/python/bin`, `$AMIGA_TOOLCHAIN/bin`, `$AMIGA_PREFIX` and the directory of
`$FSUAE_ARM` on `PATH`, in that order, so `python3`, `m68k-amiga-elf-gdb`, `vasmm68k_mot` and
`fs-uae` (the native arm64 one) resolve to the shared copies. It takes amiga-debug's x86_64
`$AMIGA_PREFIX/fs-uae` off `PATH`; a project that needs that build names it in `FSUAE`.

Other shared files have no variable of their own:

| File | What |
|---|---|
| `Kickstarts/kick33180.A500`, `kick37175.A500` (+ `.RTB`) | Kickstart 1.2 and 2.04 (A500+), for testing slaves on them |
| `ndk/` | NDK 3.2 Release 4 (`Include_I/`, `Include_H/`, Autodocs) |
| `kalms-c2p/` | Mikael Kalms' c2p routines; vendor the ones used (playbook §10) |
| `python/` | Python 3.12 with Pillow, numpy, capstone and amitools (`xdftool` reads and writes ADFs) |
| `docs/` | this repo's `docs/`, start at `docs/index.md`; links into `share/` point at the installed copies |
| `*.md` at the top level | copies of the playbooks, for projects that name them there; new references use `docs/playbooks/` |

## Shared tools

`make whdload share` installs the single pinned WHDLoad 20.1 developer package at
`$AMIGA_SHARE/WHDLoad`, including the runtime binary, headers and KickEmu sources.
The shared shell and Python defaults use this stable path. The old `WHDLoad-20.0` path is
retired without an alias: projects that hardcode it must be updated during their own work.
Old WHDLoad installations are discarded after the replacement package is verified;
setup neither maintains nor backs up older developer versions. Files already
copied into a project's game drive or vendored sources remain unchanged until that project's
normal staging/update process runs. A shared upgrade does not establish per-game compatibility
or byte-identical rebuilds. Explicit paths outside these shared locations remain overrides.

Run scripts that launch through `fsuae_common.sh` share its settings: `AMIGA_SETUP` selects a
whole machine (`AMIGA_SETUP=a1200-fast amiga/run.sh`), `EXTRA_ARGS` overrides single options,
`DETERMINISTIC=1` makes runs repeat, `AMIGA_MONITOR` picks the display and `FSUAE_TITLE` names
the window. The contracts are in [the shared launcher](reference/headless-fsuae.md#the-shared-launcher),
[named machine setups](reference/headless-fsuae.md#named-machine-setups) and
[window options](reference/headless-fsuae.md#sound-window-screenshots). `make share` installs updates.

| What | Use | Replaces the per-project |
|---|---|---|
| `amigaxdev.env` | `path(NAME)`, `tool('objdump')`: the shared defaults with environment overrides | `local_env.py`, inline `AMIGA_TOOLCHAIN` lookups |
| `amigaxdev.barto` | `load(trace)`, `Trace.instructions(field)`, `capture_part_starts()`; honours `NAME.pc-base` | `barto.py` |
| `amigaxdev.gdbserve` | `Server(name, root, commands={...}).main(argv)`: serve / one-shot commands through the gdb stub (`stop`, `cont`, `gdb`, `shot`, `profile`, `wait`, `until`, `quit`; `commands` add or replace). `shot`, `profile`, `Server.capture` and `profile(g, n, file)` remove the old output first and raise `CaptureError` (an `ERROR` reply) on a gdb error, a disconnect, or a missing, partial or wrong-length trace, leaving no output file | per-project gdb servers |
| `amigaxdev.callprofile` | `Reduction(marks, tally).feed(trace)` per chunk, `.tree()`, `.inclusive()`, `.dma_shares()`, `.save()`/`.load()`: chunked traces reduced to self/inclusive cycles with SP-rebuilt call stacks, per-field totals and timestamped marks | per-project trace reducers |
| `amigaxdev.aprof` | instruction-profile accounting and call trees; [contracts](reference/measurement-method.md#shared-instruction-profile-reader) | per-project profile readers |
| `amigaxdev.native_service_scope` | explicit return/interrupt scope records from the optional instrumented build; [contracts](reference/measurement-method.md#explicit-native-service-scopes) | per-project native-service accounting |
| `amigaxdev.disasm` | `python3 -m amigaxdev.disasm dis\|disd\|hotspots [--label NAME] ...` | `dis.sh`, `disd.py`, `hotspots.py` |
| `amigaxdev.adf`, `amigaxdev.patchlist` | `python3 -m amigaxdev.adf DISK`, `python3 -m amigaxdev.patchlist SLAVE OFFSET` | `adf.py`, `patchlist.py` |
| `amigaxdev.release` | `archive(prefix, files, drawer_icon, dos_stamp(y, m, d))`, `write()`, `refuse_originals()`, `installer_icon(icons_dir, appname)` | the body of `package_release.py`, `installer_icon.py` |
| `amigaxdev.mac` | `macbin`, `resource_fork`, `hfs_extract`, `gen_trap_names`, `m68k_sweep` | the Macintosh ports' copies |
| `amigaxdev.dos` | `mz_info` (with Compack detection), `verify_amiga_runtime` | the DOS ports' copies |
| `amigaxdev.framework` | `python3 -m amigaxdev.framework diff\|sync PROJECT`: the port's framework against `$AMIGA_FRAMEWORK` | — |
| Ghidra scripts | `DumpCallGraph`, `ExportListing`, `ExportAuditListing`, `DumpZeroPage`, `MacMarkEntries`, `MacApplyNames`, `MacDumpTraps` (Ghidra started from the project root: they read `ghidra_scripts/entrypoints.csv` and `tmp/trap_names.lua` there) | the identical per-port copies |
| `whdload/SmokeSlave.s` | assemble with `-I.` and a project `smoke_name.i` holding the name line | `whdload/SmokeSlave.s` |
| `fsuae_prepare`, `FSUAE_CLAIM_STRICT=1` | in `fsuae_common.sh`: claim for DEBUG=1 else stop the previous run; a strict claim that never takes a busy port | the `run.sh` claim block |

Project-specific names (`KICKSTART_RTB`, `WHDLOAD_HOST_KICKSTART`, `FSUAE`, `GDB`, ...) stay
in the projects, defined from these. `FSUAE` is deliberately not shared: a project chooses its
build ([which FS-UAE](reference/headless-fsuae.md#which-fs-uae)), and without one the native
`fs-uae` on `PATH` (`$FSUAE_ARM`) runs.

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

`$AMIGA_SHARE/mac-runtime` holds canonical memory, QuickDraw, resource, clock and audio helpers for
Macintosh ports. Consumers vendor identical source files
and verify their own `manifest/shared-runtime.sha256` before compilation and host checks.
Use the [runtime helper index](../share/mac-runtime/README.md) to choose a helper and
find its contract and update workflow. Game-specific trap ABI
and memory ownership checks remain in each port.
