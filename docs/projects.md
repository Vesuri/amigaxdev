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
| Legends of Valour | W | migrated; keeps WHDLoad 19.2 and its native vasm build deliberately | — |
| Powerdrome | W | migrated | — |
| Stellar 7 | W | migrated; NTSC is its default | — |
| Pokeri | P | migrated; keeps WHDLoad 19.2 for its slave and tests | — |
| Revs | P | migrated; keeps WHDLoad 19.2; tests use their own `WHDLOAD_BIN` | — |
| Slicks | P | migrated; keeps WHDLoad 19.2; unstripped `SlicksDiag.exe` differs on every build (stripped release identical) | — |
| Vette | P | migrated; keeps WHDLoad 19.2 | — |
| Alone in the Dark | P | migrated; keeps WHDLoad 19.2, its fixed port 24377 and its own machine arguments; uses the shared `fs-uae-aprof` | — |
| Rescue on Fractalus | P | migrated; keeps WHDLoad 19.2 | — |
| Secret Weapons of Luftwaffe | P | migrated; its tests take Unicorn from `AMIGA_UNICORN` | — |
| Downwell | P | migrated; its HEAD did not build before the change (`MotionBinary64`), generated files identical | — |
| Stunt Car Racer | P | migrated (no run script); `tools/test_whdload.py` keeps WHDLoad 19.2 as the binary releases were validated with | — |
| Red Baron | F | migrated (harness in `tmp/dev`, playbook reference on the branch) | harness probes `w1_build_modes.py`, `probe_menu.py` hardcode `~/.local` paths |
| 4D Sports Driving | F | migrated (harness in `tmp/dev`) | — |
| Hard Drivin' | F | on the shared environment from the start (harness in `tmp/dev`; slave changes, VERIFY variants and performance docs on the branch) | — |
| Indianapolis 500 JOTD | F | harness in `tmp/dev` migrated; uncommitted slave work untouched | — |
| Indianapolis 500 StingRay | F | migrated (harness in `tmp/dev`) | — |

Not Amiga game projects, left alone: dA JoRMaS (an Amiga demo repo; it already uses
`fsuae_common.sh`, whose old functions are unchanged), Excellence, PETSCIIRobots-SDL, Tutka,
amiberry, pt2-clone, Apartment, Lego.

What migrated means: the project's `amiga/env.sh` sources the shared one, its run scripts launch
through the shared `fsuae_options`, and its tools take the toolchain from the environment. Its
builds were byte-identical before and after, and its FS-UAE command lines differ only in sound
and window for debug and warp runs. FS-UAE's own log is now under `.run/fsuae/Cache/Logs/`
(the launcher sets `--base_dir`).

## Changes in the shared tree that reach every project

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

## Shared code still copied per project (later)

Byte-identical or near-identical copies that could move here once the setup migration is done:
`barto.py` (six WHDLoad repos identical), `adf.py`, `patchlist.py`, the gdb-server skeleton
(`td2.py` and its descendants), the Ghidra scripts (identical except `@category`), the dA JoRMaS
framework in eight ports, `test_whdload.py` and `package_release.py`.

Python tools that start FS-UAE themselves, so they are not silent and come to the front: Rescue
on Fractalus `tools/test_whdload.py`, `tools/test_rom_failures.py`; Alone in the Dark
`tools/test_whdload.py`, `tools/install-data/test_installer_script.py`,
`tools/install-data/test_amiga.py`. Every `run.sh` that honours `DEBUG=1` repeats "claim the
port, else stop the previous run"; that could be one shared function.

Rule violations found on the way, for each project's owner: `/tmp` scratch files (Test Drive 2,
Battlehawks, Indianapolis 500 `fixed_window.sh`/`profile_demo.sh`; Rescue on Fractalus), Rescue on
Fractalus `audio_ridge.py` suggests a `/tmp` path; `core.hooksPath` not `/dev/null` in Alone in
the Dark, Rescue on Fractalus, Revs (an absolute path), Vette and Stunt Car Racer; the Red Baron
harness probes `w1_build_modes.py` and `probe_menu.py` hardcode `~/.local` paths.
