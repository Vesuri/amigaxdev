# Running FS-UAE for automated work

How the projects boot, probe and stop FS-UAE without anyone at the keyboard. It applies to
source ports and WHDLoad projects alike; the WHDLoad playbook adds the trace profiler
([§5](../playbooks/new-game-playbook.md#5-attach-the-debugger-and-get-a-trace-with-pcs-in-it)).
Measure, don't theorise: this loop has settled timing and rendering bugs in every port where
reading the code did not.

- [The shared launcher](#the-shared-launcher)
- [Which FS-UAE](#which-fs-uae)
- [Booting a program from directory drives](#booting-a-program-from-directory-drives)
- [The gdb stub](#the-gdb-stub)
- [The diag-run pattern](#the-diag-run-pattern)
- [Reading results](#reading-results)
- [Sound, window, screenshots](#sound-window-screenshots)
- [Machines, warp and determinism](#machines-warp-and-determinism)
- [Sharing the machine](#sharing-the-machine)
- [Pitfalls](#pitfalls)

## The shared launcher

Every run script starts the same way:

```sh
cd "$(dirname "$0")"
. ./env.sh                 # the project's amiga/env.sh, which sources the shared env.sh
. "$FSUAE_COMMON"
```

`fsuae_common.sh` (installed from `share/`) gives each directory its own emulator and gdb-stub
port. Set the machine variables, then call `fsuae_options` once and launch with only the
drives and program options:

| Call | Does |
|---|---|
| `fsuae_options` | fills `FSUAE_ARGS` from `AMIGA_MODEL`, `CPU`, `CHIP_KB`, `FAST_KB`, `SLOW_KB`, `KICKSTART`, `NTSC`, `WARP`, `DEBUG`, `DEBUG_WAIT`, `DETERMINISTIC`, `RECORD`, `JOY0`/`JOY1`, `SOUND`, `WINDOW` |
| `fsuae_launch ARGS...` | background start; logs to `$FSUAE_LOG` (default `.run/fsuae.log`), records the pid, prints it. `$FSUAE_PID` is the emulator itself |
| `fsuae_exec ARGS...` | the same in the foreground, for interactive `run.sh` |
| `fsuae_claim_port` | before a `DEBUG=1` run: picks a free `$DEBUG_PORT`, killing only this directory's leftover |
| `fsuae_prepare` | what a `run.sh` does before launching: `fsuae_claim_port` for `DEBUG=1`, otherwise stops this directory's previous run. `FSUAE_CLAIM_STRICT=1` makes the claim never take or move a port: any listener on `$DEBUG_PORT`, even this directory's, makes it fail (for a fixed port, Alone in the Dark) |
| `fsuae_stop` | kills the tracked emulator; safe in `trap fsuae_stop EXIT` |
| `fsuae_gdb_script F` | a copy of a checked-in `.gdb` with `127.0.0.1:NNNN` patched to `$DEBUG_PORT` |

- **The launcher resolves repeated options before starting FS-UAE.** It takes `$EXTRA_ARGS`
  first, then `AMIGA_SETUP` machine arguments (if selected), then the script's arguments,
  then `FSUAE_ARGS`, so `EXTRA_ARGS` overrides everything.
  Prefer the variables (`CHIP_KB=2048`) to `EXTRA_ARGS=--chip_memory=2048`; a script that
  appended `EXTRA_ARGS` last once measured the dev machine instead of the target (Revs).
- `fsuae_options` runs once: `fsuae_launch` reuses an existing `FSUAE_ARGS`. Set every variable
  before calling it. Named machine settings are reapplied at launch.
- The port defaults to `2345 + cksum($PWD) % 400`, so a checkout always gets the same one.
  `DEBUG_PORT=N` pins it; a pinned port held by another project stops the script instead of
  taking the port.
- FS-UAE's own log goes to `.run/fsuae/Cache/Logs/fs-uae.log.txt` (`--base_dir`), separate per
  directory, instead of the default FS-UAE directory's log that every project shares.
- The window title says whose window it is and what it runs: `PROJECT · MACHINE · gdb PORT`,
  for example `F1GP · 68030 MMU AGA 2MB CHIP 8MB FAST · gdb 2565`. PROJECT is the outermost
  checkout's directory name (a clone or worktree in a checkout's `tmp/` counts as that
  checkout), and the port appears for `DEBUG=1`. MACHINE is what FS-UAE built after the
  model's defaults, checked every field: the CPU (`68EC020` for 24-bit addressing), `MMU` and
  `FPU` when present, the chipset, `NTSC`, then chip, slow and fast RAM (fast counts Zorro II,
  Zorro III and motherboard RAM). It reads `FS-UAE` until the first field. The launcher passes
  `--title='PROJECT · {machine}'`; `FSUAE_TITLE=TEXT` or an explicit `--title` replaces it and
  may use `{machine}` too. The native builds show it in FS-UAE's drawn title bar, in capitals,
  and as the macOS window name (`patches/fsuae-window-title.patch`; upstream ignores `--title`,
  draws FS-UAE and renames the window to an fps counter); the bundled x86_64 build still
  shows FS-UAE.
- Parallel runs from one checkout need distinct `FSUAE_RUN` and `DEBUG_PORT`
  (Slicks `pc_profile.sh`: `FSUAE_RUN=.run/pcprof-$LABEL`).

## Named machine setups

Select a machine with one variable when invoking a project's normal launcher:

```sh
AMIGA_SETUP=a1200-fast amiga/run.sh
AMIGA_SETUP=a1200-040 DEBUG=1 amiga/run.sh
```

| `AMIGA_SETUP` | Model / chipset | CPU / nominal clock | Chip KB | Slow KB | Fast KB | MMU | FPU |
|---|---|---|---:|---:|---:|---|---|
| `a500` | A500 / OCS | 68000 / 7 MHz | 512 | 512 | 0 | none | none |
| `a500-1.5m` | A500 / OCS | 68000 / 7 MHz | 512 | 1536 | 0 | none | none |
| `a500+` | A500+ / ECS | 68000 / 7 MHz | 1024 | 0 | 0 | none | none |
| `a3000` | A3000 / ECS | 68030 / 25 MHz | 2048 | 0 | 8192 | 68030 | 68882 |
| `a1200` | A1200 / AGA | 68EC020 / 14 MHz | 2048 | 0 | 0 | none | none |
| `a1200-fast` | A1200 / AGA | 68EC020 / 14 MHz | 2048 | 0 | 8192 | none | none |
| `a1200-030` | A1200 / AGA | 68030 / 50 MHz | 2048 | 0 | 8192 | 68030 | none |
| `a1200-040` | A1200 / AGA | 68040 / 25 MHz | 2048 | 0 | 8192 | 68040 | 68040 |
| `a1200-060` | A1200 / AGA | 68060 / 50 MHz | 2048 | 0 | 8192 | 68060 | 68060 |

`a500-1.5m` is the playbooks' A500-equivalent: most WHDLoad slaves need more than the 512 KB
trapdoor expansion of `a500` (Prince of Persia's ExpMem alone is about 820 KB).

All presets disable JIT and extra Zorro III/motherboard RAM. They select Kickstart 3.1:
`kick40063.A600` for the 68000 models and A3000, and `KICKSTART_A1200` (`kick40068.A1200`) for A1200.
This preserves directory hard-drive boot support; these are not original factory ROM setups.
`a3000` uses 8 MB of Zorro II Fast RAM and the shared ECS ROM for directory drives,
rather than the original motherboard RAM/SCSI configuration. Set `KICKSTART_A3000` to
a user-supplied A3000 ROM to override its ROM selection.
`NTSC` remains a separate setting, retaining the project's default. Stock clocks follow it
(PAL: 7,093,790 / 14,187,580 Hz; NTSC: 7,159,090 / 14,318,180 Hz).

All 68020-and-faster presets enable instruction-cache emulation through the compatible
CPU core. The 68030/040/060 presets also enable data-cache emulation
(`uae_cpu_data_cache=true`) and use `uae_uaeboard=full+indirect`, required to retain data
caches with directory hard drives. They work with `DETERMINISTIC=1`: the indirect board runs
traps and directory-drive packets on host threads, and `fsuae-determinism.patch` runs those in
lockstep with the emulation (below). The 68020 has no data cache. `uae_cachesize=0` refers
to the disabled JIT translation cache, not the emulated CPU caches. Guest software still
controls its cache registers; WHDLoad games need the game's `CACHE` option when appropriate.
For a data-cache comparison, request the override through `EXTRA_ARGS` and verify the
effective runtime setting as described below.

The full 030 has its MMU; the 040 and 060 have their integrated MMU and FPU. The 040/060
presets use the non-cycle-exact MMU core: their nominal clock is configured, but that core
does not honour hardware timing. Use these for functional/MMU checks, not performance
comparisons (playbook §8). These settings do not add WHDLoad's `MMU` option to a game's
command line.

`fsuae_options` sets and exports `AMIGA_MODEL`, `CPU`, `CHIP_KB`, `FAST_KB`, `SLOW_KB`
and `KICKSTART`. `fsuae_launch` and `fsuae_exec` reapply the selection and put its arguments
ahead of project machine arguments, including hardcoded models, RAM and MMU settings.
An unknown nonempty name fails before launch. With `AMIGA_SETUP` unset or empty, existing
behaviour is unchanged. A preset wins over individual machine variables; use `EXTRA_ARGS`
for a deliberate exception, for example `EXTRA_ARGS='--fast_memory=4096'`.

**Override precedence:** `EXTRA_ARGS`, then the named preset, then caller arguments,
then generated defaults; the first occurrence within that order wins. The launcher
removes duplicate keys and competing RAM/FPU/CPU aliases, including raw UAE options.
`--cpu=68040-NOMMU` also overrides a lower-priority MMU setting; an explicit MMU or FPU
setting in the same group wins in either order, so `--cpu=68030 --uae_mmu_model=0` and
`--uae_mmu_model=0 --cpu=68030` are both a 68030 without MMU (as is `--cpu=68EC030`, which has
no FPU either). A CPU name FS-UAE does not know (`68030-NOMMU`) fails before launch: FS-UAE
would only warn "Unknown CPU specified" and run the model's default CPU, a 24-bit 68020 on an
A1200, with data-cache emulation turned off. The launcher compares names as FS-UAE does,
ignoring case and anything but letters, digits and `+`. JIT enablement requests
an 8 MB translation cache unless a higher-priority explicit cache size is supplied;
installed native builds reject JIT because they were compiled without it.

Examples: `EXTRA_ARGS='--cpu=68040-NOMMU --uae_cpu_data_cache=false'` disables the MMU
and data cache without changing the preset's clock. `EXTRA_ARGS='--zorro_iii_memory=32768'`
(or `--uae_z3mem_size=32`) adds 32 MB Zorro III RAM while retaining other preset settings.
High-level RAM values use FS-UAE's units; raw `*_size` options use UAE's units.

Check `Cache/Logs/debug.uae` and the final `CPU=..., MMU=..., JIT=...` runtime report
before measuring. Argument acceptance is insufficient, especially with private builds
or config files. `debug.uae` records the requested values: when FS-UAE fixes up the
configuration it keeps them, for example `cpu_data_cache=true` after "Data cache emulation
requires Indirect UAE Boot ROM." (data-cache emulation with a directory drive but no indirect
board) or "...68030+ only." Such fixups precede the runtime report in
`Cache/Logs/fs-uae.log.txt`, each as `[UAE] [000] TEXT` followed by TEXT on a line of its
own; FS-UAE's option warnings such as "Unknown CPU specified" are lines of their own too.
`python3 scripts/test_fsuae_config.py` exercises real native-emulator settings on both launch
paths, including defaults, NOMMU, a 68030 without MMU, cache, Z3, unsupported JIT and an
unsupported CPU name, and fails on any fixup.
This establishes configuration/functionality, not timing accuracy.

Install with `make share`; projects sourcing the installed shared launcher pick it up on
their next run without repository edits. This does not change scripts that launch FS-UAE
directly or source a private copy. It also cannot rewrite staging, validation or diagnostic
labels that a project computes before calling the shared launcher. In particular, Alone
in the Dark's `AMIGA_CONFIG` label still describes its own configuration, and its validation
can reject inputs before launch. A machine preset does not imply that a game's CPU/chipset
or memory requirements are met; many WHDLoad games cannot run in the stock A500 RAM sizes.
Specialised wrappers that set machine options in `EXTRA_ARGS` still override the preset.

Launcher regression checks (argument capture only, no emulator or game data):
`python3 scripts/test_fsuae_setup.py` from AmigaXDev. They exercise `/bin/bash` 3.2,
both launch paths, every preset, conflicting project arguments and the override order.

## Which FS-UAE

| Binary | Variable | Use |
|---|---|---|
| x86_64 Barto build (Rosetta), `~/.local/fs-uae/fs-uae` | `fs-uae` on `PATH` | the default `fs-uae` on `PATH` for run, debug and diag scripts; host lldb can attach to it, and its trace profiler needs lldb to set the profiled window (WHDLoad playbook §5) |
| native arm64 build | `FSUAE_ARM` | several times faster for long diagnostics and 68030 runs; drives keyboard input and whole fields from gdb (below); lldb cannot attach, but without a trigger it profiles the whole 24-bit space, so no window fix is needed |
| arm64 with the cycle profiler | `$AMIGA_SHARE/fs-uae-aprof/fs-uae` | exact emulated cycles per PC between `monitor aprof start` and `monitor aprof stop FILE`; cycle-exact 68020–68060 loops without an MMU model (Alone in the Dark `aprof.sh`; Red Baron `aprof_flight.py` for 040/060) |

A project selects one with `FSUAE` (Alone in the Dark: `diag_run.sh` prefers `FSUAE_ARM` when
`FSUAE` is unset). Matching clock settings across binaries do not make their memory timing
identical: compare measurements from one binary only.

## Booting a program from directory drives

The port pattern: `dh0` is a boot volume whose `s/startup-sequence` is
`C:SetPatch QUIET` (AGA only), `cd dh1:`, then the program name; `dh1` holds a copy of the
executable. gdb reads the `.elf` from `out/`.

- **Keep `cd dh1:` and the bare name on separate lines.** `--remote_debugger_trigger=NAME`
  matches the name the shell runs. A single `dh1:RoF` line stopped the trigger matching: gdb
  resolved symbols at base `$7500` and no breakpoint ever hit. A `$7500` base means the trigger
  did not match (Rescue on Fractalus).
- `cd` is a ROM shell built-in from Kickstart 2.0. Kickstart 1.3 does not boot from a directory
  drive at all; test 1.3 under WHDLoad's `kick13` KickEmu (Revs `test_whdload.py`).
- Pass `--window_width`/`--window_height`. Without them FS-UAE started from a non-GUI shell
  stalls with "Not a valid drawable size for glViewport".
- Give runs a `--state_dir` under `.run/` and delete its `.uss` files before an interactive
  run. A diag run can leave a state saved while the CPU sat halted on a grey first frame;
  resuming it makes any build look frozen (cost hours of false bisecting on the Atari port that
  Revs inherited).
- AGA programs need the user's `SetPatch` (`$SETPATCH`) copied onto the boot volume.

### WHDLoad startup memory and saved-file completion

`SplashDelay=0` does not disable the configurable-options splash. For tight-memory
qualification, test `ConfigDelay=0` separately and record both settings. Ferrari
Formula One on a 2 MiB Chip-only 020 failed ExpMem allocation with WHDLoad 20.1's
configuration splash but completed the same startup with it disabled. Version 17
still needed more memory in that configuration. A required API version is not a
promise of identical memory requirements across runtime versions.

A successful native save dialog or `resload_Abort(TDREASON_OK)` is not enough to
prove persistence or successful exit. WHDLoad normally buffers writes until exit.
Keep the emulator running until the system prompt is visible, verify the new file
in the host directory, then close it. Use a new filename so an old file cannot
produce a false pass. Compare complete saved contents with the native reference;
scripted calendar changes during loading may legitimately change the original
file's timestamp fields.

In Ferrari Formula One's 020+Fast directory-drive tests, both enabled and legacy
paths stalled in WHDLoad file-cache cleanup after creating a new season file on
20.0 and 20.1. The documented `NoWriteCache` option made the 20.1 enabled save
persist and returned to AmigaDOS. Preserve the failing controls and qualify the
working option explicitly; do not infer a general hardware/runtime defect from
this emulator-specific observation. CPU-cache options such as `NoCache` are
separate from `NoWriteCache`.

## The gdb stub

The Barto stub in both FS-UAE builds, driven by `m68k-amiga-elf-gdb`.

### Harness commands (native builds)

`patches/fsuae-harness.patch` goes into every native build `scripts/build-fsuae.sh` makes
(`FSUAE_ARM`, `FSUAE_APROF`), not into the x86_64 one:

| Command | Does |
|---|---|
| `monitor key RAW 0\|1` | queues raw Amiga key code `RAW` (hex) as pressed (1) or released (0) on the emulated keyboard, exactly as a host key would arrive; works with the window in the background or with no window |
| `monitor fields N` | runs N whole PAL/NTSC fields (1–6000) and stops again at the last vsync, where the reply comes. From a stop at a vsync (the end of `fields` or `profile`, a Ctrl-C) that is N vsyncs; from any other stop (breakpoint, step, the reset stop) the first vsync ends the partial field, so N + 1 |
| `monitor mouse DX DY` | adds DX, DY (decimal, at most ±127) to the port-0 mouse counters, as host mouse motion would; works with `JOY0=none` |
| `monitor input EVENT N` | sends an emulator input event by its config name with state N (decimal, 1 press, 0 release): `JOY1_FIRE_BUTTON` and `JOY1_2ND_BUTTON` are the port-0 mouse buttons, `JOY2_LEFT`, `JOY2_FIRE_BUTTON` and so on the port-1 joystick. Emulator actions (`SPC_*`) are refused |
| `monitor harness` | prints supported commands; check capabilities before use. `exact-fields gapless-profile` mark the vsync stops below; a build without them runs N + 1 fields after every stop and leaves a field untraced between `profile` chunks |
| `monitor input-state` | observes CIA-A SDR and the last guest-read PRA/POTGOR values with read counters; it neither polls host devices nor acknowledges interrupts |
| `monitor profile N "" FILE` | traces N whole fields, from a vsync to a vsync, and stops at the last one. After a stop at a vsync it starts there, so chained chunks leave no gap; after any other stop it starts at the next vsync. With no `--remote_debugger_trigger` the PC window is the whole 24-bit space instead of the stub's uninitialised `[0x0100007f, +0)` |

Together they replace input tapes: stop, send input, `fields`, release, `fields`, with
`profile` chunks between input events. The run is exactly repeatable with
`WARP=1 DETERMINISTIC=1 JOY0=none` (Prince of Persia: identical per-PC cycles, field totals
and frame timestamps across boots) except for what host timing decides: a Ctrl-C lands at
whichever vsync is current when it arrives. `patches/fsuae-determinism.patch` removes two
reads of uninitialised host memory that made runs differ: the serial port's break detection
(`checkreceive_serial` used an unset `breakcond`; in some runs Paula then received zeros and
raised RBF every character period once the guest set SERPER, visible in INTREQR) and the
chipset frame buffer (screenshots include columns the chipset never draws: the two rightmost
of an A500 screen held leftover host memory). The same patch fixes deterministic mode with the
indirect UAE board, which every data-cache preset uses. Upstream deterministic mode handles
directory-drive packets on the emulation thread, but with that board each guest memory access
waits for the 68k, which runs on the same thread, so the boot hung at `FS: dh0 ... starting`.
Now the host trap and filesystem threads run in lockstep: after each handoff the emulation
thread waits until no host thread runs, so their effects land at the emulated instant of the
handoff (`trap_lockstep_*` in `src/traps.cpp`). Without deterministic mode nothing changes.
`scripts/test_fsuae_repeat.py [FS-UAE] [SETUP...]` boots the A1200 and A500 3.1 ROMs with no
disk and runs breakpoint, `fields`, chained `profile`, register-read and Ctrl-C stops twice; the
runs must agree on registers, beam position, chip RAM and every trace byte, the guest's own field
counter (`GfxBase->VBCounter`) must advance by exactly the fields each command ran, and chained
chunks must match one unbroken profile. On `a1200-030`, `a1200-040`, `a1200-060` and `a3000` it
boots a directory drive whose startup-sequence writes a file line by line, twice, stopping every
25 fields: the runs must agree on registers, chip RAM and the file at every stop and on Fast RAM
at the end, the file must be complete, and the emulator log must not say it turned data-cache
emulation off. Bad arguments, an unknown event and an unknown command
all reply with an error, which gdb prints as `Protocol error with Rcmd` (an unquoted
`profile` FILE does too, even without spaces: write `"FILE"`); a script that only reads
replies misses it, so call `amigaxdev.gdbserve.require_harness(g, "mouse", ...)` first.
It raises with the fix when the build is older. `scripts/test_fsuae_input.py [FS-UAE]` boots
the Kickstart 1.3 ROM with no disk and reads mouse and joystick input back from JOY0DAT and
JOY1DAT. The input observer verifies both mouse buttons and keyboard press/release through
guest-visible values. PRA/POTGOR are latched by guest reads: require their read counters
to advance after an action before trusting the value. Repeated observations while
stopped must leave values and counters unchanged. This is an input-test instrument,
not a general CIA register reader.

**Stops at a vsync are parked.** The end of `fields` or `profile`, and a Ctrl-C while the CPU
runs (the stub reads packets from a running CPU only at a vsync), stop the CPU inside the vsync
handler, exactly at the field boundary, not at the next instruction. A parked stop serves
memory reads and writes, the harness commands, queries, `monitor fields`, `monitor profile` and
continue in place. Register reads, steps, breakpoint and watchpoint changes and other monitor
commands first move the stop to the next instruction boundary, a few cycles into the next field
(or line 312 when the CPU is in STOP), where a stop always used to be; the field still counts
as begun at the vsync, so `fields N` from there is still N. A `profile` after that starts at
the next vsync, so one field runs untraced: keep register reads out of a chain of chunks. gdb
reads registers after a Ctrl-C and after `maintenance flush register-cache`, not after a
`monitor` command. Parking changes no emulation: the old and new stubs give identical
registers, traces and chip RAM at the same field.

**A profiled field does not run exactly like an unprofiled one.** With the profiler and DMA
recording on, the 68020 core runs differently: booting the A1200 ROM, d1 at the start of the
next field held 3822148 after an unprofiled field and 3822145 after a profiled one, and the
runs stay apart from there. Both are repeatable; but a route that profiles different fields
reaches a different state, so compare captures only between runs that profiled the same fields.
The 68000 core showed differences only in the recorded DMA data of the next field.

- **Move the mouse in steps and let fields run between them.** The counters are 8 bits, so a
  game that reads them once a field loses a larger delta; Gunship moves in steps of at most
  64 counts with 2 fields after each. A game that reads its pointer position gives a closed
  loop: move, run fields, read the position, repeat (Ferrari Formula One).
- **Hold a button or key for several fields**: a game that polls once a frame misses a
  press and release within one field. Release everything held before ending a run.

Use `amigaxdev.input.Input` with the CPU stopped. It checks capabilities, records
commands/replies, rejects protocol errors and releases its held inputs in reverse order:

```python
from amigaxdev.input import Input
with Input(g, log=write_action) as controls:
    controls.button("JOY2_FIRE_BUTTON", True)
    controls.fields(10)
    controls.button("JOY2_FIRE_BUTTON", False)
    controls.move_to((120, 80), read_game_pointer)
```

`read_game_pointer` and gameplay assertions belong to the project; motion is bounded
and fails if the pointer does not converge. Cleanup attempts every release even when
one fails, then reports the failure. Do not treat sending input as proof of gameplay.

Key codes:
cursor `4c-4f`, Return `44`, Space `40`, Esc `45`, Ctrl `63`, left Shift `60`, keypad digits
`0f 1d 1e 1f 2d 2e 2f 3d 3e 3f` (0–9).

A rebuild changes the binary hash. Projects that pin the hash of a shared build must re-pin
after `make setup` rebuilds it.

- **Reads work, writes are dropped silently.** `set var` on a global, an array element or
  emulated memory reads back unchanged, with no error (Revs, Rescue on Fractalus; WHDLoad
  projects saw the same: `M`/`P`/`G` packets are ignored). Put every stimulus in the binary: a
  `-D` flag with a VBL-count window (Rescue on Fractalus `FORCE_*`), a startup-sequence
  argument (Slicks), or a slave option. `.gdb` scripts only read.
- **Attach within `--remote_debugger=N` seconds** of launch (`DEBUG_WAIT`, default 20). Without
  a trigger the stub stops serving after that.
- Connect to `127.0.0.1`, not `localhost` (IPv6). The stub accepts one client: wait for the
  port with `lsof -nP -iTCP:$DEBUG_PORT -sTCP:LISTEN`, never by connecting to it.
- Run gdb with `-q -l 10`, `HOME` and `XDG_CACHE_HOME` pointing into `.run/`, and a preamble of
  `set pagination off`, `set confirm off`, `set remotetimeout 90`, `target remote`.
- **Emulated time stops while gdb holds the CPU**, so stops cost no emulated time but a stop
  inside a timed window distorts host-side pacing. Quote timings only from scripts with no stop
  in the window.
- **A conditional breakpoint slows the emulator below real time**: gdb evaluates the condition
  on the host, with a stub round trip, on every hit. One on a per-render function ran Revs at
  about 0.4× real time: 45 s of wall bought 18 emulated seconds, against 288 s for the same warp
  script with a plain `continue`. Count in the program and print once at the end.
- **gdb interrupts are serviced at vsync only**, so gdb PC sampling is vsync-locked and distorts
  shares (Slicks: C2P doubled, car physics hidden). Use a target-side sampler; see
  [measurement method](measurement-method.md).
- **A gdb script aborts at the first unknown symbol**, from that line on. Deleting or renaming a
  probe global silently empties every `.gdb` that prints it; grep `*.gdb` when you do, and read
  "output stops after the header" as a stale script (Rescue on Fractalus).
- **`--gc-sections` drops unused probe globals**, and gdb then resolves the name into `.text` and
  prints instruction bytes, not 0 (Revs read `painted=1223110688`). Keep the probe list in the
  Makefile as `--undefined=` roots and audit it on every link
  ([port toolchain](port-toolchain.md#link-audits)).
- **Older builds can report stale SR flags.** Current native build recipes apply the
  [register observer fix](register-observer.md); verify the selected binary was rebuilt.
  After monitor-driven execution, also flush GDB’s register cache. For cache-backed
  memory discrepancies, see the optional [cache observer](cache-observer.md).
- `until` blocks the server until its address is reached. Prefer `break *A`,
  `ignore $bpnum N`, `continue`.
- The stub stops on CPU exceptions: an address error or illegal instruction stops with a usable
  backtrace (the framework's `GCC-PORT.md`). It also accepts hardware watchpoints, but one did
  not fire in Indianapolis 500: prove a watchpoint on a known write before trusting its silence.
- `dump binary memory FILE A B` works; a 1 MiB dump takes a few seconds. gdb splits arguments
  at spaces and repo paths often contain them (`Their Finest Hour`), so run gdb from the harness
root and dump to a repo-relative path (`tmp/x-code.bin`); pass `tempfile.mkdtemp(dir='tmp')`,
which returns an absolute path, through `os.path.relpath`. gdb types
  `a0`–`a7` as pointers; symbols without debug type need a cast.
- An error inside a breakpoint's `commands` leaves gdb waiting at its prompt: end every
  scripted path in `quit`, and keep a deadline outside gdb.
- **The remote debugger greys the display.** A headless run proves state and cost, never
  appearance.

## The diag-run pattern

Revs `amiga/diag_run.sh` is the template (Rescue on Fractalus, Vette and the other ports copy
it):

1. Stage `dh0`/`dh1`, `fsuae_claim_port`, `DEBUG=1 fsuae_options`, `fsuae_launch` with the
   drives, trigger, window size and state dir.
2. Poll up to 60 s for the stub port, giving up as soon as the emulator pid dies.
3. Start gdb in the background with the preamble and `$GDBSCRIPT`, output to
   `.run/gdb-out.log`.
4. Wait the deadline in 1 s steps, returning early when gdb exits.
5. SIGINT gdb (breaking its `continue`); allow it time to print; SIGINT again; `kill -9` the
   gdb pid; `fsuae_stop`.
6. Print a filtered tail of the log (`GDBTAIL`, default 40 lines).

The fixture variant (Slicks `debug.sh "" fixture.gdb`): break on named marker functions, print
`KEY=value` records in `commands … silent`, end with `quit` (pass) or `quit 1`, and exit with
gdb's status, with `trap fsuae_stop EXIT`.

- **The `continue` after setup is load-bearing.** Without it gdb runs the script at connect time,
  while the program is still halted at the trigger, and every counter reads 0.
- **The deadline is a safety ceiling, not success.** A timeout SIGINT makes gdb run the next
  line as if the breakpoint had hit: a chord-less control "passed" Revs' quit test that way.
  Judge a verdict by where gdb stopped (compare `$pc` with the breakpoint address), and require
  an explicit PASS record.
- Break an out-of-line function by address: a symbolic `break` resolved to three locations in
  Revs, one inside an inlined copy.
- Validate the instrument in the same output: a build fingerprint, `*_INVALID` records when
  profile flags or frame counts are wrong (Slicks), sanity lines such as `accounted ≈100%`
  (Revs).

## Reading results

- **Read `.run/gdb-out.log`, not the script's stdout.** The 40-line tail drops headers and early
  phases; a Revs frame total summed from it read 36 ms low. Copy the log to a per-arm file as
  soon as a run ends and compute from that.
- **A failed run leaves the previous log in place.** When FS-UAE never starts, gdb exits at
  once and the tail prints yesterday's output. Check `date; ls -l .run/gdb-out.log`, or grep for
  a string only the new script prints.
- **A live `diag_run.sh` is not a live run**: the script sits out its deadline after the
  emulator is gone. Check for the `fs-uae` pid.
- FS-UAE echoes every option into its log, misspelt and unimplemented ones included
  (`--volume=0` is unimplemented). The config dump is not evidence that an option took effect;
  check from outside (below).

## Sound, window, screenshots

On macOS, shared **debug/diagnostic launches** automatically place new windows on the
**leftmost display when multiple displays are active**. This uses the same classification
as quiet runs: `DEBUG=1`, `WARP=1`, `FSUAE_QUIET=1`, or `--warp_mode=1` in `EXTRA_ARGS`.
Ordinary interactive launches (including plain `run.sh`) keep their usual placement;
`DEBUG=1 amiga/run.sh` gets debug placement. With one display, automatic placement stays
unchanged. Explicit `AMIGA_MONITOR` choices apply to both interactive and debug runs. The display
arrangement is read at each launch using CoreGraphics (no Accessibility or Screen Recording
permission required). Coordinates use logical desktop points, including negative coordinates
for displays to the left of or above the primary display.

Override the choice independently of the emulated machine:

```sh
AMIGA_MONITOR=right AMIGA_SETUP=a1200-fast amiga/run.sh
AMIGA_MONITOR=primary amiga/run.sh
AMIGA_MONITOR= amiga/run.sh  # disable automatic positioning
```

`left` and `right` select the displays with the smallest and largest desktop x origins;
ties prefer the topmost display, then the primary display. `primary` selects the macOS
main display. The window's top-left corner is placed 40 points inside the selected display;
its size is unchanged. This controls windowed launches, not initial fullscreen placement.
`EXTRA_ARGS='--window_x=... --window_y=...'` overrides the chosen coordinates.
The launcher also passes the effective coordinates and window dimensions through
`FSEMU_WINDOW_X/Y/W/H`. The bundled x86_64 window code ignores command-line positioning
and recentres the window unless these internal dimensions are set. Both launch paths
derive them from the final arguments, retaining explicit coordinate and size overrides.

Headless launches (`WINDOW=none` or an effective `--video_driver=null`) skip display discovery.
An explicit invalid selection or failed explicit display lookup stops the launch. Automatic
lookup failure reports the problem and keeps ordinary placement. Existing windows are not
moved. After `make share`, every project using `fsuae_launch`/`fsuae_exec` gets this behaviour
without project changes. Private launchers are unaffected.

Monitor checks: `python3 scripts/test_monitor.py` and `python3 scripts/test_fsuae_setup.py`.

Debug runs (`DEBUG=1`, `WARP=1`, `FSUAE_QUIET=1`, or `--warp_mode=1` in `EXTRA_ARGS`) get
`--audio_driver=dummy` and a window behind the others (`SDL_MAC_BACKGROUND_APP=1`); plain runs
are audible and in front. `SOUND=1|0` (`SILENT=1`) and `WINDOW=front|back|none` override;
`none` adds `--video_driver=null`.

- Paula keeps running with the dummy driver, so silent runs measure the same: a silent arm
  re-measured 17.181 ms against 17.194 audible (Revs). Check that sound is off with
  `lsof -p PID | grep -ic CoreAudio` (3 normally, 0 with dummy).
- Audio capture: `SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=/absolute/path` with
  `--audio_driver=sdl` (Slicks `debug.sh`).
- Interactive screenshots: hold F12, press S. The directory comes from `FSEMU_SCREENSHOTS_DIR`
  (point it into `tmp/`); `--screenshots_output_dir` is parsed but ignored.
- Headless frames: `dump binary memory` the chunky buffer or bitplanes and decode on the host
  (Slicks `tools/verify_amiga_frame.py`); WHDLoad projects take screenshots from one-field
  traces (playbook §5). macOS denies screen capture to FS-UAE, and posted key events never
  reach it.
- Keyboard joystick: `keyboard_key_*` is ignored by these builds; `--joystick_port_1=keyboard`
  gives arrows plus right Ctrl/Alt. `JOY1=none` also sets the port's mode to nothing, which
  keeps the host mouse out of a capture.

## Machines, warp and determinism

- Size the machine with `CHIP_KB`/`FAST_KB`/`SLOW_KB` and time only on the target
  configuration. Diagnostic Fast RAM (Vette: 2 MiB Chip + 8 MiB Fast) is for room, never for
  timing.
- A faster CPU exposes beam-timing races: `AMIGA_MODEL=A1200` alone missed a sprite-pointer
  race that `EXTRA_ARGS=--cpu=68040` triggered (Revs).
- `WARP=1` is for correctness runs. It leaves emulated quantities unchanged (Revs: ~4.9× faster,
  same ratios), but a benchmark fixture should refuse it (Slicks).
- Fixed-clock CPU settings and their pitfalls (`68040-NOMMU`, `cpu_speed=max` is not a real
  machine) are in playbook §8; audit the FS-UAE log for overrides before trusting a speed
  figure (Pokeri).
- `DETERMINISTIC=1` and `RECORD=FILE` (which implies it) give repeatable runs for replay,
  on every preset including the data-cache ones ([what deterministic mode covers](#harness-commands-native-builds)
  and `scripts/test_fsuae_repeat.py`).

## Sharing the machine

Several projects run emulators at once.

- **Never `pkill fs-uae` or `pkill gdb`**, and never kill an emulator you did not start. The
  launcher kills only what this directory started: the pid recorded in `.run/fsuae.pid` (a
  leftover only if it is still an `fs-uae`), or, in `fsuae_claim_port`, an `fs-uae` whose working
  directory is this one. Kill your own gdb by its pid.
- **Do not trust copied startup headers as runtime configuration evidence.** This FS-UAE
  logger opens a shared `fs-uae.log` under its user-data directory, then copies it when
  switching to the project-private log (`libfsemu/src/log.c`). Simultaneous project boots
  can therefore mix or omit the early `cpu =` / `ntsc_mode =` text without changing either
  emulator's configuration. Stellar 7 observed a 68060/PAL header followed by the correct
  private 68030/NTSC UAE options. Retain the private effective `debug.uae`, inspect the
  final `Set option` values and corroborate the running game's clock. Do not kill other
  projects or reinterpret a mismatched header as a measured machine change.
- `Remote connection closed` mid-run usually means another session killed your emulator, not
  that your build crashed. Revs read three such runs as "the PROBES build dies past vbi 262"
  before finding a sibling project's `pkill`. Check `pgrep -fl "diag_run.sh|fs-uae"` first. A
  killed run is not a slow run: discard its timing.
- One capture at a time per checkout: two parallel captures broke both debugger sessions
  (Legends of Valour). One run directory has one owner.
- Close every emulator you start.

## Pitfalls

- **Source `env.sh` in the same shell command as the run.** Agent tool calls do not share a
  shell; otherwise `fs-uae` is "not found", gdb exits, and the old log is read as the new one.
- **Stale builds.** A Makefile that tracks neither `-D` flags nor headers links stale objects
  into a working-but-wrong binary. Treat a regression right after a flag toggle or header edit
  as a stale build until `make clean` rules it out
  ([port toolchain](port-toolchain.md#rebuilds-and-flags)).
- **Don't rebuild while a run is live**: gdb reads symbols from `out/*.elf` in place, and a
  rebuild with other flags no longer describes the running program.
- **Don't edit a shell launcher while it runs**: bash resumes reading at stale file offsets
  (Pokeri). For long validations run a frozen copy of the exe and elf.
- **After editing a shared harness script, rerun a known-good control** on an unchanged binary
  in the same session. Two legs failing at once, including a control that had just passed,
  exposed a harness edit that would otherwise have shipped as "1.3 doesn't work" (Rescue on
  Fractalus).
- `run.sh` scripts that change directory before copying files must resolve relative arguments
  against the caller's directory first (Indianapolis 500).
- **A C variable named like its struct tag** (`struct rt_pointer rt_pointer`) parses as the type
  in a C++ frame (`syntax error ... &rt_pointer`), even after `set language c`; a script that
  stops in C code works, the same line at a C++ breakpoint fails and leaves gdb waiting on
  stdin with FS-UAE alive. Export an address under a unique name for scripts (SWOTL).


### Cached 040/060 MMU write attributes

All native builds apply `patches/fsuae-mmu-write-cache.patch` to the pinned Barto
core. Six ordinary/locked byte/word/long ATC write-hit paths incorrectly loaded
cache attributes from the independent read entry. This could make CHIP writes
copy-back despite write-through/noncacheable page descriptors, leaving stale DMA
pixels. Use the write entry for both translation and attributes. The build stamp
includes the correction hash, so old binaries are rebuilt on setup.

Wing Commander reproduced this with both CPU caches enabled: 259 of 306 intro
conversions differed from physical DMA pixels while CPU pixels matched. The
corrected emulator passed 306 intro and 120 in-game conversions; a matched build
without the correction failed 19 of its first 20 conversions. Normal frontend
captures and user play-testing confirmed the visible fix. No guest cache flushes
or cache disabling were needed. These checks establish 040 correctness in those
windows, not 060 coverage or hardware timing calibration.

`FSUAE_MMU` (`$AMIGA_SHARE/fs-uae-mmu-fixed/fs-uae`) names the build that carried the
correction before every native build did. `make setup` neither builds nor updates it, so it
lacks the later patches; use `FSUAE_ARM` or `FSUAE_APROF`. A retained project-local debugger
binary needs rebuilding; changing an environment variable cannot patch an old binary.


## Verify explicit CPU-frequency scaling

`patches/fsuae-cpu-frequency.patch`, applied to every native build, carries the expression
below. Before it, every `AMIGA_SETUP` preset (they all pass `uae_cpu_frequency`) ran too fast
on native builds: the A500's 68000 got cycle unit 231 instead of 256, 10.8% fast, 157481 CPU
cycles per PAL field instead of 142102 (Prince of Persia). A500 figures measured with a preset
on an older native build are inflated by that much; re-measure them.

Before using a named MHz profile for performance claims, inspect the running
core's `baseclock`, `cpucycleunit` and configured frequency. Older FS-UAE source
calculates `CYCLE_UNIT * baseclock / cpu_frequency` with a 32-bit intermediate.
PAL `512 * 28375160` overflows: a requested 50 MHz reports cpucycleunit 32,
where the intended integer result is 290. Ferrari Formula One exposed this
during accelerated qualification. Configuration text alone did not reveal it.

Widening the multiplication alone is insufficient. `baseclock` is eight times
Chip clock, whereas `get_cycles()` advances by CYCLE_UNIT per Chip clock.
The expected explicit-frequency expression is
`(uae_u64)CYCLE_UNIT * (baseclock / 8) / currprefs.cpu_frequency`.
Cross-check it against the stock 020 multiplier: explicit 14.18758 MHz must
produce unit 128, matching the default 020, not 1024. A requested 50 MHz gives
integer unit 36, about 50.445 MHz of cycle budget; report the quantization.
Check both live metadata and independently observed cycle/field counts.
Preserve rejected captures; the first widened-only fix (unit 290 at requested
50 MHz) also used the wrong units. Default-clock profiles are unaffected. The
project-local calibration passes: stock and explicit 020 settings produce
identical complete DMA rows, 284,204 cycles per field, and driving-clock state
across 1,000 fields. Shared installed binaries remain unchanged.

## Project debugger extensions and memory discovery

Private debugger extensions have limits that need checking on the exact build.
TFX's stub accepted roughly 20 software breakpoints and required `tfxmem` writes
below about 90 bytes; 32-byte chunks were reliable. These are observations about
that extension, not limits guaranteed by the shared debugger. Read writes back,
and synchronize CPU caches before execution and before comparing result memory;
debugger memory access can bypass dirty cache lines. See the
[cache observer](cache-observer.md).

Discover executable hunks from the configured memory ranges and validate the
complete hunk chain. Auxiliary hunks may load below the main code allocation;
TFX's initially narrow search rejected a valid legacy executable. Derive hook
locations from the active patch configuration: an optional frame-display hook
cannot locate the slave when that option is off. Separate failure to discover or
reach the gameplay checkpoint from a game crash.
