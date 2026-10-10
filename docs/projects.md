# The projects

Every project is its own repo next to this one. This page records what each takes from the
shared environment and what remains to change so that it takes *only* that. Nothing below has
been changed in any project yet; the migration is paused.

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
| Test Drive 2 | W | clean | recipe 2, 3, 5 (vendored KickEmu and headers, also shipped by `package_release.py`) |
| Their Finest Hour | W | clean | 2 (no `KICKSTART_A1200`, `WHDLOAD`), 3, 4, 5; stale playbook path in `CLAUDE.md` |
| Battlehawks 1942 | W | clean | Kickstarts from `~/Documents/RetroPie/BIOS` (`env.sh`, `run.sh`, `tools/bh_report.py`); 2–6; paths into other projects in docs |
| Indianapolis 500 | W | clean | 2, 3, 4; stale playbook path |
| Legends of Valour | W | clean | 2 with WHDLoad 19.2 kept as its deliberate default (set before the source line); 3, 4; `makefile` prefers a repo-local vasm |
| Powerdrome | W | **active, skip** | 2–5 |
| Stellar 7 | W | **active, skip** | 2–5 |
| Pokeri | P | clean | 2, 3, 4 |
| Revs | P | clean | 2, 3, 4; `LHA` default points at a missing `~/.local/opt/lha` |
| Slicks | P | clean | 2, 3, 4; `LHA` default as Revs; SetPatch is now 40.16 (was 45.25) |
| Vette | P | clean | 2, 3 |
| Alone in the Dark | P | untracked aprof files (another session) | 2, 3; its aprof build now lives in AmigaXDev (`patches/fsuae-aprof.patch`, same sha) |
| Rescue on Fractalus | P | untracked files | Kickstart from RetroPie; `LHA` default as Revs; 2, 3; `/tmp` use |
| Secret Weapons of Luftwaffe | P | **active, skip** | Kickstart from RetroPie; fixed toolchain and `openjdk@21` paths; SetPatch now 40.16; its patched dosbox-x build stays in its repo |
| Downwell | P | **active, skip** | Kickstart from RetroPie; 2, 3, 4 |
| Stunt Car Racer | P | uncommitted work | no `amiga/env.sh`; makefile defaults to WHDLoad 19.2 |
| Red Baron | F | **active, skip** | committed tools and docs on the branch; harness `tmp/dev` |
| 4D Sports Driving | F | **active, skip** | harness `tmp/dev` |
| Indianapolis 500 JOTD | F | all work uncommitted | harness `tmp/dev`; the playbook calls it abandoned |
| Indianapolis 500 StingRay | F | clean branch | harness `tmp/dev` (ignored, not in git) |

Not Amiga game projects, left alone: dA JoRMaS (an Amiga demo repo; it already uses
`fsuae_common.sh`, whose old functions are unchanged), Excellence, PETSCIIRobots-SDL, Tutka,
amiberry, pt2-clone, Apartment, Lego.

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

Rule violations found on the way, for each project's owner: `/tmp` scratch files (Test Drive 2,
Battlehawks, Indianapolis 500 `fixed_window.sh`/`profile_demo.sh`; Rescue on Fractalus), and
`core.hooksPath` not `/dev/null` in Alone in the Dark, Rescue on Fractalus, Revs (an absolute
path), Vette and Stunt Car Racer.
