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

- **FS-UAE keeps the first value of a repeated option.** The launcher passes `$EXTRA_ARGS`
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
| `a500+` | A500+ / ECS | 68000 / 7 MHz | 1024 | 0 | 0 | none | none |
| `a1200` | A1200 / AGA | 68EC020 / 14 MHz | 2048 | 0 | 0 | none | none |
| `a1200-fast` | A1200 / AGA | 68EC020 / 14 MHz | 2048 | 0 | 8192 | none | none |
| `a1200-030` | A1200 / AGA | 68030 / 50 MHz | 2048 | 0 | 8192 | 68030 | none |
| `a1200-040` | A1200 / AGA | 68040 / 25 MHz | 2048 | 0 | 8192 | 68040 | 68040 |
| `a1200-060` | A1200 / AGA | 68060 / 50 MHz | 2048 | 0 | 8192 | 68060 | 68060 |

All presets disable JIT and extra Zorro III/motherboard RAM. They select Kickstart 3.1:
`kick40063.A600` for the 68000 models and `KICKSTART_A1200` (`kick40068.A1200`) for A1200.
This preserves directory hard-drive boot support; these are not original factory ROM setups.
`NTSC` remains a separate setting, retaining the project's default. Stock clocks follow it
(PAL: 7,093,790 / 14,187,580 Hz; NTSC: 7,159,090 / 14,318,180 Hz).

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
| x86_64 Barto build (Rosetta), `~/.local/fs-uae/fs-uae` | `fs-uae` on `PATH` | the default for run, debug and diag scripts; host lldb can attach to it, which the WHDLoad trace profiler needs |
| native arm64 build | `FSUAE_ARM` | several times faster for long diagnostics and 68030 runs; lldb cannot attach, so the profiler window has to be set from the guest (playbook §5, Legends of Valour) |
| arm64 with the cycle profiler | `$AMIGA_SHARE/fs-uae-aprof/fs-uae` | exact emulated cycles per PC between `monitor aprof start` and `monitor aprof stop FILE`; cycle-exact 68020/68030 loops only (Alone in the Dark `aprof.sh`) |

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

## The gdb stub

The Barto stub in both FS-UAE builds, driven by `m68k-amiga-elf-gdb`.

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
- **The SR in the stub is stale** (UAE updates it lazily): tell supervisor from user code by
  which stack SP is in.
- `until` blocks the server until its address is reached. Prefer `break *A`,
  `ignore $bpnum N`, `continue`.
- The stub stops on CPU exceptions: an address error or illegal instruction stops with a usable
  backtrace (the framework's `GCC-PORT.md`). It also accepts hardware watchpoints, but one did
  not fire in Indianapolis 500: prove a watchpoint on a known write before trusting its silence.
- `dump binary memory FILE A B` works; a 1 MiB dump takes a few seconds. gdb splits arguments
  at spaces and repo paths often contain them, so dump to a repo-relative path. gdb types
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
- `DETERMINISTIC=1` and `RECORD=FILE` (which implies it) give repeatable runs for replay;
  see [validation harness](validation-harness.md).

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
