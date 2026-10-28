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
   projects. `AGENTS.md` leads into AmigaXDev's docs and tools as in docs/environment.md,
   "A project's agent instructions".

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
| F1GP | W | on the shared environment from the start | — |
| Mercenary 3 | W | on the shared environment from the start | — |
| Prince of Persia 2 | P | on the shared environment from the start | — |
| Wing Commander | P | on the shared environment from the start | — |
| X-Wing | P | on the shared environment from the start | — |
| Ferrari Formula One | F | on the shared environment from the start (StingRay worktree, harness in `tmp/dev`) | — |
| Road Rash, Gunship, Grand Prix Circuit, TFX, Test Drive | F | on the shared environment from the start (JOTD worktrees, harness in `tmp/dev`) | — |

The fork worktrees belong to two main checkouts, `jotd_whdload_slaves` (JOTD's repository) and
`Stingray_WHDLoad_Patches` (StingRay's), which have no harness of their own.

Not Amiga game projects, left alone: dA JoRMaS (an Amiga demo repo; it already uses
`fsuae_common.sh`, whose old functions are unchanged), Excellence, PETSCIIRobots-SDL, Tutka,
amiberry, pt2-clone, Apartment, Lego.

What migrated means: the project's `amiga/env.sh` sources the shared one, its run scripts launch
through the shared `fsuae_options`, and its tools take the toolchain from the environment. Its
builds were byte-identical before and after, and its FS-UAE command lines differ only in sound
and window for debug and warp runs. FS-UAE's own log is now under `.run/fsuae/Cache/Logs/`
(the launcher sets `--base_dir`).

## Changes in the shared tree that reach every project

What changed under projects that use the shared files, and what a project does about it. The
contracts are in the linked docs; git has the details.

- **Native FS-UAE builds** (`FSUAE_ARM`, `FSUAE_APROF`) apply the frequency, harness,
  determinism, MMU-write and window-title patches ([which FS-UAE](reference/headless-fsuae.md#which-fs-uae)).
  Presets with an explicit CPU frequency ran about 10.8% fast on a 68000 before the frequency
  patch. Every rebuild changes the binaries' hashes: projects that pin them (Prince of Persia 2,
  Ferrari Formula One) re-pin and re-measure.
- **Field counts after a vsync stop:** `monitor fields N` after the end of `fields` or `profile`
  or a Ctrl-C now runs N fields (it ran N + 1), and the next `profile` leaves no field untraced
  ([harness commands](reference/headless-fsuae.md#harness-commands-native-builds)). A route that
  counts fields or polls `profile 1` screenshots for a checkpoint must be recounted.
- **Determinism:** otherwise identical runs agree, and `DETERMINISTIC=1` boots directory drives
  on `a1200-030`, `a1200-040`, `a1200-060` and `a3000`, where it used to hang
  ([machines, warp and determinism](reference/headless-fsuae.md#machines-warp-and-determinism)).
  A matrix that turned deterministic mode off for those presets can turn it back on.
- **CPU names:** the launcher refuses names FS-UAE does not know, such as `--cpu=68030-NOMMU`
  (FS-UAE ran a 24-bit 68020 instead), and an explicit `--uae_mmu_model` or `--uae_fpu_model`
  beats the one a `--cpu` name implies in either order
  ([named machine setups](reference/headless-fsuae.md#named-machine-setups)). Figures taken with
  such a name were not the CPU they claim; a 68030 without MMU is `--cpu=68EC030` or
  `--cpu=68030 --uae_mmu_model=0`.
- **Window titles** name the project, the machine FS-UAE runs and the gdb port; `FSUAE_TITLE` overrides them
  ([the shared launcher](reference/headless-fsuae.md#the-shared-launcher)).
- **Captures:** `amigaxdev.gdbserve` raises `CaptureError` instead of leaving an old image or
  trace behind ([shared tools](environment.md#shared-tools)). Project commands that call
  `capture` see the exception.
- **WHDLoad:** `WHDLoad/` holds the only developer package, 20.1; `WHDLoad-20.0/` is retired
  without an alias ([shared tools](environment.md#shared-tools)). The migration byte-identity
  checks below describe the path migration, not a rebuild against the new package.
- **ROMs and SetPatch:** `kick40068.A1200` is the TOSEC `[!]` dump; A1200 measurements taken
  before 2026-10-10 used Harry Sintonen's `mathieeesingbas.library` fix (revision 40.69), kept in
  `~/.local/share/amiga/.replaced/`. `kick37175.A500` is the A500+ `[!]` dump, with an RTB.
  `SetPatch` is 40.16 from Workbench 3.1 (was 45.25 from AmigaOS 3.2).

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
