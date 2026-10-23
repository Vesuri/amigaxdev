# The projects

Every project is its own repo next to this one. This page records what each takes from the
shared environment and how far each is migrated.

## Migration recipe (per project)

1. `git status` clean and no emulator or capture of the project running; otherwise skip it.
2. `amiga/env.sh` sources the shared `env.sh` (docs/environment.md); project-specific values go
   before the source line. Compare the effective variables before and after.
3. Run scripts call `fsuae_options` / `fsuae_launch` (or `fsuae_exec`) from the shared
   `fsuae_common.sh` and pass only their drives and game options. Compare the FS-UAE command
   line before and after with a stub `FSUAE`; the only intended differences are sound and
   window behaviour in debug runs.
4. Python tools take the toolchain from `AMIGA_TOOLCHAIN` (default `~/.local/opt`), never a
   fixed `~/.local/opt/bin/...`.
5. Vendored copies that are byte-identical to the shared tree go: the build takes
   `$(WHDLOAD)/Include` and `$(WHDLOAD)/Src/sources`. The slave must build byte-identically.
   Release packaging that ships those sources (Test Drive 2 `tools/package_release.py`) takes
   them from `$WHDLOAD`. Patched copies stay.
6. Docs: point the playbook references at AmigaXDev `docs/playbooks/`; drop paths into other
   projects.

## Status

Groups: **W** WHDLoad-improvement repo (playbook), **P** source port, **F** branch of JOTD's or
StingRay's slave repository (harness in the ignored `tmp/dev/`).

| Project | Group | State | Needs |
|---|---|---|---|
| Test Drive 2 | W | migrated | — |
| Their Finest Hour | W | migrated | — |
| Battlehawks 1942 | W | migrated | — |
| Indianapolis 500 | W | migrated | — |
| Legends of Valour | W | migrated; uses `WHDLoad/`; retains its native vasm build | — |
| Powerdrome | W | migrated | — |
| Stellar 7 | W | migrated; NTSC is its default | — |
| Pokeri | P | migrated; uses `WHDLoad/` for its slave and tests | — |
| Revs | P | migrated; uses `WHDLoad/`; tests use their own `WHDLOAD_BIN` | — |
| Slicks | P | migrated; uses `WHDLoad/`; unstripped `SlicksDiag.exe` differs on every build (stripped release identical) | — |
| Vette | P | migrated; uses `WHDLoad/` | — |
| Alone in the Dark | P | migrated; uses `WHDLoad/`, its fixed port 24377 and its own machine arguments; uses the shared `fs-uae-aprof` | — |
| Rescue on Fractalus | P | migrated; uses `WHDLoad/` | — |
| Secret Weapons of Luftwaffe | P | migrated; its tests take Unicorn from `AMIGA_UNICORN` | — |
| Downwell | P | migrated; its HEAD did not build before the change (`MotionBinary64`), generated files identical | — |
| Stunt Car Racer | P | migrated (no run script); `tools/test_whdload.py` uses the shared `WHDLoad/` path | — |
| Red Baron | F | migrated (harness in `tmp/dev`, playbook reference on the branch) | — |
| 4D Sports Driving | F | migrated (harness in `tmp/dev`) | — |
| Hard Drivin' | F | on the shared environment from the start (harness in `tmp/dev`; slave changes, VERIFY variants and performance docs on the branch) | — |
| Indianapolis 500 JOTD | F | harness in `tmp/dev` migrated; uncommitted slave work untouched | — |
| Indianapolis 500 StingRay | F | migrated (harness in `tmp/dev`) | — |
| Prince of Persia | F | on the shared environment from the start (harness in `tmp/dev`; keyboard route driven with `monitor key`) | — |

Not Amiga game projects, left alone: dA JoRMaS (an Amiga demo repo; it already uses
`fsuae_common.sh`, whose old functions are unchanged), Excellence, PETSCIIRobots-SDL, Tutka,
amiberry, pt2-clone, Apartment, Lego.

What migrated means: the project's `amiga/env.sh` sources the shared one, its run scripts launch
through the shared `fsuae_options`, and its tools take the toolchain from the environment. Its
builds were byte-identical before and after, and its FS-UAE command lines differ only in sound
and window for debug and warp runs. FS-UAE's own log is now under `.run/fsuae/Cache/Logs/`
(the launcher sets `--base_dir`).

## Changes in the shared tree that reach every project

- Native FS-UAE builds (`FSUAE_ARM`, `FSUAE_APROF`, `FSUAE_MMU`) apply
  `fsuae-cpu-frequency.patch` and `fsuae-harness.patch`. The first changes timing: presets with
  an explicit CPU frequency (all `AMIGA_SETUP` names) ran about 10.8% fast on a 68000 before it.
  Each rebuild changes the binaries' hashes; projects that pin them (Prince of Persia 2,
  Ferrari Formula One) re-pin and re-measure.
- The native builds' gdb stub parks stops made at a vsync (`exact-fields gapless-profile` in
  `monitor harness`; docs/reference/headless-fsuae.md). After the end of `fields` or `profile`
  or a Ctrl-C, `monitor fields N` now runs N fields (it ran N + 1), and the next `monitor
  profile` starts at that vsync (it left one field untraced). A route that counts fields, or
  polls `profile 1` screenshots for a checkpoint, reaches its checkpoint at a different field
  number and must be recounted; after a breakpoint or step `fields N` still runs N + 1.
  `fsuae-determinism.patch` makes otherwise identical runs agree: before it the serial port
  could raise RBF in INTREQR in some runs and not others, and A500 screenshots had two columns
  of leftover host memory. It also lets `DETERMINISTIC=1` boot directory drives on the
  data-cache presets (`a1200-030`, `a1200-040`, `a1200-060`, `a3000`), which used to hang at
  `FS: dh0 ... starting`.
- The launcher refuses a CPU name FS-UAE does not know, such as `--cpu=68030-NOMMU`, before
  starting anything; FS-UAE used to run a 24-bit 68020 instead. A 68030 without MMU is
  `--cpu=68EC030` or `--cpu=68030 --uae_mmu_model=0`. An explicit `--uae_mmu_model` or
  `--uae_fpu_model` now beats the one a `--cpu` name implies when both come from the same
  place (`EXTRA_ARGS`, the preset, the script's arguments, `fsuae_options`), whatever their
  order; `--cpu=68030 --uae_mmu_model=0` used to keep the MMU.
- Native emulator windows are titled `PROJECT · DIRECTORY · gdb PORT` instead of FS-UAE
  (docs/reference/headless-fsuae.md); `FSUAE_TITLE` overrides it.
- `amigaxdev.gdbserve`'s `shot`, `profile` and `Server.capture` remove the output file before
  capturing and raise `CaptureError` (an `ERROR ...` reply) when gdb fails, the stub
  disconnects or the trace is missing, partial or has the wrong number of fields. Before,
  a failed `shot` saved the previous `shot.bin`'s image under the new name and replied as if it
  had worked, and a failed `profile` left any older file at the target. Project commands that
  call `capture` now see the exception.
- `WHDLoad/` contains the sole active WHDLoad 20.1 developer package (including its runtime).
  `WHDLoad-20.0/` is retired without an alias; hardcoded references must be fixed during
  project work. Shared defaults use `WHDLoad/`; older-version comments do not pin the
  installed version. Existing staged
  binaries and vendored sources remain unchanged. The migration byte-identity checks below
  describe the path migration, not validation of a rebuild against the new developer package.

- `kick40068.A1200` is now the TOSEC `[!]` dump. The old file was Harry Sintonen's
  `mathieeesingbas.library` fix (revision 40.69); A1200 measurements taken before 2026-10-10
  used it. The old file is in `~/.local/share/amiga/.replaced/`.
- `kick37175.A500` is now the A500+ `[!]` dump (the old one matched no TOSEC entry), with an RTB.
- `SetPatch` is 40.16 from Workbench 3.1 (was 45.25 from AmigaOS 3.2).
- The default gdb-stub port of every directory changed (400 values instead of 40). Scripts
  read `$DEBUG_PORT` after sourcing `fsuae_common.sh`, and tools parse the port from the run
  script's output, so nothing depends on the number.
- The Python environment `~/.local/share/amiga/python` is new; it comes first on `PATH` only
  for projects that source the shared `env.sh`.

## Shared tools and what stays per project

AmigaXDev ships the copied tools once (docs/environment.md, "Shared tools"): `barto.py`,
`local_env.py`, `adf.py`, `patchlist.py`, `dis.sh`/`disd.py`/`hotspots.py`, the gdb-server
skeleton, the release archive and icon code, the Mac and DOS helpers, the identical Ghidra
scripts, the smoke slave, and the claim-or-stop block of the run scripts. A project's tools find
the package through `tools/_amigaxdev.py`; `python3 -m amigaxdev...` needs `. amiga/env.sh`
first (or `PYTHONPATH=$(AMIGA_PYLIB)` in a Makefile).

Each switch was verified like the setup migration: the project's report and frame tools give
the same output on a stored trace, each gdb server ran `shot`, `profile 2` and a game command
against a live emulator, and archives, smoke slaves and Ghidra exports are byte-identical.

| Switched | Kept on top of the shared code |
|---|---|
| Test Drive 2, Battlehawks 1942, Their Finest Hour, Indianapolis 500, Indianapolis 500 JOTD and StingRay harnesses | `i500.py` and `tfh.py` export `SOCK` for their state tools |
| Powerdrome | its gdb server's PD1 request framing, captures of up to 500 fields |
| Legends of Valour | its boot, capture (both window modes, `.pc-base`), multi-address `until`, `gdb` handshake |
| Stellar 7 | its lldb profiler-window fix; `run.sh` uses the launcher's `NTSC` and `SLOW_KB` |
| Red Baron and Hard Drivin' harnesses | Red Baron's `until`; Hard Drivin's instances, `host`, `poke`, long `profile`, `barto_mmap.py` |
| 4D Sports Driving harness | a `stop` that interrupts only a running target, the native profiler's window check, its own `hotspots.py` (address ranges, `--sum`, `--jt`) |
| Pokeri, Slicks, Vette | their release file maps; Pokeri's save slots |
| Alone in the Dark | `require_production`, scratch in `tmp/`; `tools/resource_fork.py` re-exports the shared module for its 124 importers; `FSUAE_CLAIM_STRICT=1` |
| Secret Weapons of Luftwaffe, Revs, Rescue on Fractalus | their CPU-specific Ghidra scripts; Secret Weapons of Luftwaffe's and Rescue on Fractalus' `run.sh` use `fsuae_prepare` |
| Downwell | its own tools (none of the copied ones); `run.sh` uses `fsuae_prepare` |

Red Baron's committed branch `tools/` stay standalone, because the branch is meant for JOTD's
repository.

Stays in each project, because it is the game's own: `frames.py`, `swap_fields`,
`check_disabled`, `fixed_window.sh`, `compare_*`, `audit_hooks`, `state_*` (frame counters and
state at game addresses), the game commands of the gdb server, `release/Install`, `diag_run.sh`,
`check_release.py` and `test_whdload.py` (per-game checks), `stage_original_data.sh`, the
transpilers and translators, and the Ghidra scripts tied to one original CPU or machine
(`MarkEntries` CSV variants, `DumpHwAccesses`, `SeedLiveMap`, `ApplyNames` for Pokeri, Revs and
Rescue on Fractalus).

The dA JoRMaS framework stays vendored in each port: converging the copies would change every
port's binary except Slicks' and Secret Weapons of Luftwaffe's (which share theirs byte for byte).
`$AMIGA_FRAMEWORK` is the canonical tree to compare with and take fixes from
(`python3 -m amigaxdev.framework diff PROJECT`); each port's `UPSTREAM.md` (Secret Weapons of
Luftwaffe: `framework/README.md`) records the AmigaXDev commit its copy is based on.

Python tools that start FS-UAE themselves, so they are not silent and come to the front: Rescue
on Fractalus `tools/test_whdload.py`, `tools/test_rom_failures.py`; Alone in the Dark
`tools/test_whdload.py`, `tools/install-data/test_installer_script.py`,
`tools/install-data/test_amiga.py`.

Rule violations found on the way, for each project's owner: `/tmp` scratch files (Test Drive 2,
Battlehawks, Indianapolis 500 `fixed_window.sh`/`profile_demo.sh`; Rescue on Fractalus), Rescue on
Fractalus `audio_ridge.py` suggests a `/tmp` path; `core.hooksPath` not `/dev/null` in Alone in
the Dark, Rescue on Fractalus, Revs (an absolute path), Vette and Stunt Car Racer; Alone in the
Dark's smoke slave calls itself "Vette slave smoke test" (copied from Vette; kept for
byte-identical builds).
