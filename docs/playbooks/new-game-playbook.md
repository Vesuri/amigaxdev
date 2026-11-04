# Playbook: profiling another WHDLoad-installed Amiga game

For an existing project, read only the section needed for the current task. Use the
[task index](../index.md) for focused references and shared helpers. Read §0 when
starting a new project; follow the complete workflow only when setting one up.

> `$ARCHIVES` below is the directory with the game archives the user supplies. It is never
> written into a repo.

> **For a new standalone WHDLoad project.** Follow the setup steps in order and pass
> each check before moving on. For an existing project, use its own task and state;
> consult only the relevant section below. Fork projects use the
> [JOTD](new-game-playbook-jotd.md) or [StingRay](new-game-playbook-stingray.md) variant.

Reuse the shared `amigaxdev` tools ([environment](../environment.md#shared-tools)) and build
the game-specific harness on them (§3).

The end state ("ready to improve") is defined in §12. Getting there means:
1. a reproducible, cycle-exact trace of real gameplay;
2. a report saying where the frame time goes;
3. a frame-rate figure from a fixed window;
4. a written model of how game time advances.

Patches come after all of that.

---

## 0. Rules (put these in the new repo's AGENTS.md before anything else)

- **Never commit game, Kickstart or WHDLoad bytes**, or anything made from them: unpacked data,
  traces, memory dumps, screenshots, input recordings, built slaves. Keep them in `tmp/`, which
  is ignored. Start `.gitignore` from AmigaXDev's, which also ignores `*.lha *.adf *.rom
  *.slave *.bin *.png *.rec` at any depth.
- **Never `pkill fs-uae` or `pkill gdb`.** Other projects run emulators at the same time. Use
  `~/.local/share/amiga/fsuae_common.sh`, which kills only the pid this directory started and
  gives each directory its own gdb-stub port. Kill orphans of your own (a `serve`, a `gdb`, an
  FS-UAE that crashed and left its window up) by pid, after checking the pid is yours.
- Commits: use whatever author, signing, hooks and trailer conventions the user gives. In this
  repo that is `Vesa Halttunen <vesuri@jormas.com>`, unsigned, `core.hooksPath=/dev/null`, no
  Co-Authored-By lines, one commit per coherent feature. Ask if you're not told.
- Addresses in docs are **offsets into the game's code hunk or file**, using the same numbering
  as the slave's patch lists. Never quote absolute addresses, because they move with the memory
  configuration.
- **No performance claim without a measurement**, and only from the right instrument (§7, §8).
- **No local paths in the repo**: no home directories, usernames, `~/Documents/...`, RetroPie or
  amiberry locations, and no paths into other projects. Name another project without its location
  ("AmigaXDev `docs/playbooks/new-game-playbook.md`"). Shared files come from `~/.local/share/amiga`
  through overridable variables in `amiga/env.sh` (§1); scratch output goes to the repo's ignored
  `tmp/`, never `/tmp`. `~/.local` and `fsuae_common.sh` are the allowed convention.
- **History belongs in git.** Docs describe the current state (how to build, run and measure; how
  the game and the patches work; current numbers; open items). When a finding changes, update the
  reference in place instead of appending a dated section, and delete tools nothing uses.

## 1. Host prerequisites (installed by AmigaXDev)

AmigaXDev's `make setup` installs everything below and `make check` verifies it; its
`docs/environment.md` lists every shared variable. A project's `amiga/env.sh` sources the
shared `~/.local/share/amiga/env.sh` and then sets only what the project changes.

| What | Where | Check |
|---|---|---|
| FS-UAE with the Barto gdb stub (native arm64, `FSUAE_ARM`) | `~/.local/share/amiga/fs-uae-arm/fs-uae` | `fs-uae --version` after `source amiga/env.sh` |
| m68k gdb / objdump / gcc | `~/.local/opt/bin/m68k-amiga-elf-*` | `m68k-amiga-elf-gdb --version` |
| vasm (Motorola syntax) | `~/.local/vasmm68k_mot` | runs and prints usage |
| WHDLoad 20.1 (binary, includes, kickemu sources) | `~/.local/share/amiga/WHDLoad/` (env `WHDLOAD` = the directory, for `Include/` and `Src/`; `WHDLOAD_BINARY` defaults to `$WHDLOAD/C/WHDLoad`); only the latest developer package is installed | `C/WHDLoad` exists |
| Shared kill/port helper | `~/.local/share/amiga/fsuae_common.sh` | sourced by `run.sh` |
| Host Kickstart 3.1 | `~/.local/share/amiga/Kickstarts/kick40063.A600` (env `KICKSTART`) | |
| Kick images for kickemu slaves | `~/.local/share/amiga/Kickstarts/`: `kick34005.A500` + `.RTB` (env `KICK13` / `KICKSTART13`, `RTB`), `kick40068.A1200` (env `KICKSTART_A1200`, the 68020 capture machine) + `.RTB` | |
| Workbench 2.04 floppy (gives `C:` and `Libs:`) | `~/.local/share/amiga/Workbenchv2.04rev37.67Workbench.adf` (env `WORKBENCH_ADF`) | |
| LHa for UNIX (creates archives, §13) | `~/.local/share/amiga/lha-compressor/src/lha` (env `LHA`) | runs and prints usage |
| `lha` (extract), `unar`, `lldb` | Homebrew / Xcode | |
| Hardware Reference Manual, RKMs, autodocs; AGA registers | `~/.local/share/amiga/adcd21/Reference/` (env `ADCD`; `ROM_Kernel_Manuals/Hardware_Manual` is AmigaGuide text, `HTML/` has pages); `~/.local/share/amiga/AGA.Guide` (env `AGA_GUIDE`) | |
| Python 3.12 + Pillow, numpy, capstone, amitools (`xdftool` for ADFs) | `~/.local/share/amiga/python` (first on `PATH` after the shared `env.sh`) | `python3 -c 'import PIL'` |

Take every shared file from the shared `env.sh` variables, never from a path written into the
repo: `. "${AMIGA_ENV:-$HOME/.local/share/amiga/env.sh}"` at the top of `amiga/env.sh`, with any
project-specific value set *before* that line (the shared file keeps values already set).
Python tools read the same variables (`os.environ.get('AMIGA_TOOLCHAIN', ...)`). Document the
variables the project uses in its development doc. Never fall back to copies elsewhere on
the machine: if one is missing, fail loudly.

If the FS-UAE binary has changed, the lldb profiler fix (§5) needs new addresses. Do that
before anything else.

## 2. Unpack and identify the game

```sh
mkdir -p tmp/archive && cd tmp/archive && lha xq ../../Game.lha && cd -
find tmp/archive -type f | sort ; shasum -a 256 $(find tmp/archive -type f) > tmp/archive.sha256
```

There are two kinds of archive. Work out which one you have:

### Archive types

- **Pre-installed** (Retroplay style: `Game/Game.slave`, `Game/data/...`, `.info` files). This
  is everything you need.
- **Installer** (`GameInstall/Install`, `Game.slave`, often `source/Game*.s`, docs). It has no
  game data; the data comes from original disks. The installer archive is still valuable for
  **the slave's source**.

If you have only an installer and no disk images, stop and ask the user for the data. If you
have only the installed game, look for the slave source in the matching installer pack. WHDLoad
installs include `source/` more often than not, and a Retroplay pack without source may have an
installer pack that has it: ask the user for the installer pack. The ReadMe may also point to the
author's repository: StingRay's `MK1Roxxor/WHDLoad_Patches` on GitHub holds his slave sources
(`gh api 'repos/MK1Roxxor/WHDLoad_Patches/git/trees/HEAD?recursive=1'`, then fetch the raw file).
Without source, disassemble the slave: it is a normal hunk executable. **Reconstruct it so
vasm rebuilds it byte-identically** (a small slave takes one session): disassemble each code region
separately (data islands break the instruction alignment), turn PC-relative targets into
labels, emit patch lists with the `PL_` macros, and assemble with `-no-opt`. Then compare. Traps:
absolute `$4`/`$bc` operands must be written `($4).w` or vasm picks `abs.l`; `PL_S`
stores distance−2; `PL_P`/`PL_PS` store the destination relative to the list start
(`python3 -m amigaxdev.patchlist SLAVE OFFSET` decodes a list). Keep the reconstruction as the reference
(`whdload/original/`, `make original` = byte compare) and **build the patched slave on the
WHDLoad 20 KickEmu sources** (the user's requirement): `Src/slave-examples/kick13.asm` and
`kick13.s` from the shared `$WHDLOAD` tree (20.1; §10). The slave still declares
WHDLoad 17 unless it needs a v20 feature (§10).

Put the playable tree at `tmp/game/<Name>/`, exactly as `run.sh` will mount it on `DH1:`.

### Archive layout and runtime state

For a harness that keeps immutable inputs and disposable launch copies:

| Path relative to the harness | Purpose |
|---|---|
| `tmp/archives/<archive>.lha` | retained, unmodified download |
| `tmp/archives/<archive>.lha.sha256` | input archive checksum |
| `tmp/archives/<archive-stem>.files.json` | extracted-file SHA-256 manifest, keyed by relative path |
| `tmp/game/<archive-stem>/` | pristine extraction of the entire archive |
| `tmp/game/<archive-stem>/<installed-drawer>/` | `GAME`: directory containing the slave and its data |
| `tmp/build/` | rebuilt normal and VERIFY slaves, separate from the shipped slave |
| `amiga/.run/dh1/` | disposable writable copy mounted as `DH1:` for this harness |

Save games, preferences and mission tapes written during a run belong to disposable `dh1`.
Each launch starts from the same baseline. For a required saved scenario, copy selected files
out before restart and apply them to a **separate**, documented fixture tree or the runtime
copy; never silently promote a previous run’s state into the baseline. Keep fixtures ignored.
For A/B captures, use the same archive hash and fixture manifest, retain the exact selected
slave beside the trace, and check the pristine-file manifest has not changed. Capture one
run at a time per harness; distinct worktrees have distinct runtime directories and ports.

### Identify the slave and game code

**Read the slave before booting anything.** From the source, or the header at the start of the
`.slave`, record these in `docs/internals.md` (the doc on how the game and the slave work, §3):

| Field | Why it matters |
|---|---|
| `ws_BaseMemSize`, `ws_ExpMem` | how much RAM WHDLoad needs, so you can size the machine (§3) |
| kickemu include (`kick13.s`, `kick31.s`) or none | **OS game** (LoadSeg'd executable on an emulated Kickstart) or **direct game** (the slave loads disk images/files into memory and jumps in, no OS). Old slaves (before kickemu) are OS games too: such a slave calls `resload_LoadKick` and `resload_Patch`es the Kickstart image itself (trackdisk → `Disk.N`, a `LoadSeg` hook), and the game boots from `Disk.1`'s own startup-sequence |
| `slv_config` / `CUSTOM1..5` / `ws_Flags` | existing options; your patches add theirs here |
| `_patchexe` / `resload_PatchSeg` / `resload_Patch` lists | which file is the game code, which versions are supported (usually by CRC or size), and which instructions are already patched |
| the buffer-swap or copper patch, if any | often the best frame counter (for example `PL_P $0588a,set_copper`) |
| the main executable's name and size | the region finder byte-matches it (§6) |

Find the code file. For OS games it is the executable the slave LoadSegs. If the game boots
from disk images, list them (`python3 -m amigaxdev.adf Disk.1`, OFS/FFS) and read `s/startup-sequence`
to find it. **If `ws_ExpMem` is just the Kickstart size, the OS has only
BaseMem: the game and all its buffers are in chip RAM**, found in the
trace's chip snapshot rather than in the "other" memory dump. Parse the executable's hunk header
(`$3F3`, then the hunk sizes) to get each code/data/BSS hunk's file offset and size; a data hunk
can be allocated larger than its file-backed part. For direct games the code is in disk images or
raw files at an address the slave chooses; read it from the slave's `resload_DiskLoad`/`LoadFile`
calls. **The disk image may hold an ordinary hunk executable that the game's own intro loads and
relocates**: a slave may load a track-based intro to address 0 that in turn loads a multi-hunk
executable stored raw in the image (grep the image for `000003f3`). Parse it like a file. Expect
slack: a hunk can have bytes left over before its HUNK_END.
The slave's game patch offsets are then hunk-0 offsets. Confirm the hunk base from a `PL_P`/`PL_PS`
jump into the slave (`4ef9`/`4eb9 <slave address>`) minus its patch-list offset.

**Check:** you can name the code file, its version, its hunk layout, the slave type, and every
existing slave patch with its offset.

## 3. Scaffold the repo

For a new or freshly cloned personal repository, disable both commit and tag signing
in its local config. `commit.gpgsign=false` does not override `tag.gpgsign=true`
inherited from a work configuration. Check both effective values with
`git config --show-origin --get commit.gpgsign` and
`git config --show-origin --get tag.gpgsign`; both must be `false`.

```sh
git init && git config user.name ... && git config user.email ... \
  && git config --local commit.gpgsign false \
  && git config --local tag.gpgsign false && git config core.hooksPath /dev/null
mkdir -p amiga tools docs whdload
```

Start `.gitignore` from AmigaXDev's. `amiga/env.sh` sources the shared `env.sh` (§1);
`amiga/run.sh` launches through the shared `fsuae_common.sh`. Python tools import
`amigaxdev.barto` and `amigaxdev.env` through a three-line `tools/_amigaxdev.py` shim that puts
`$AMIGA_PYLIB` on `sys.path`, so a tool runs under any `python3`; the command-line helpers are
`python3 -m amigaxdev.disasm|adf|patchlist` after `. amiga/env.sh`. Write only the tools the game
needs and delete tools nothing uses. Use the §1 variables and repo-relative `tmp/` paths, and grep
before the first commit (`git grep -nE '/Users/|~/Documents|RetroPie|amiberry|/tmp/|Projects/'`).

### Harness tools

What each tool does, what comes from the shared package and what is game-specific (the names are
the ones this playbook uses):

| File | Shared or generic | Game-specific |
|---|---|---|
| `amigaxdev.barto` (shared, imported) | trace parser, all of it | nothing |
| `tools/game.py` | `Server(name, root=ROOT).main(argv)` from `amigaxdev.gdbserve`: `serve/stop/cont/shot/wait/until/gdb/profile/quit`, lldb window fix, `BOOT_BREAK` | the name; game commands go in `commands={'op': fn(server, g, rest)}` (they can replace a built-in); `profile_window=False` where the stub needs no window fix. Shared-code changes (`BASETEXT_VM` for a new FS-UAE binary) go to AmigaXDev |
| `amiga/run.sh` | host boot, DH0/DH1, startup-sequence, port claim (`fsuae_common.sh`) | `GAME`, slave file name, kick images copied to `DH0:devs/Kickstarts` (kick13 needs `kick34005.A500`+`.RTB`; kick31 needs `kick40068.A1200`+`.RTB`; direct slaves need none) |
| `tools/game_report.py` `regions()` | byte-match voting, BPTR chain to the data hunk | code file path and hunk offset/size, kick image (or none), slave path; `Namer` function starts (`link a5` is Aztec C; SAS/C and asm differ, see §8). For a direct game, parse the hunk file from the disk image, vote each file-backed hunk into the dump *or* the trace's chip snapshot, and find the live slave (§6) |
| `tools/frames.py`, `tools/swap_fields.py` | DMA slot counting, blitter-poll counting | frame marker (§7), interrupt-handler addresses (Kick 1.3 level-3 `$FC0D14`/BLIT `$FC0D38`/VERTB `$FC0D4A` only apply to a kick13 game; a direct game has its own handlers, read the level-3 vector at `$6C`) |
| `tools/profile_demo.sh`, `tools/ingame.py` | boot, poll, trace, dump | the "in gameplay" pixel test (a colour that only gameplay shows at a fixed pixel) |
| `tools/fixed_window.sh` | calibrate-then-reboot, retained slave, `STATE_ONLY`/`SWAP_ONLY`/`SERVE_WAIT` | anchor offset and the state watched at the anchor (§6) |
| `tools/state_fields.py`, `tools/state_writers.py` | per-field snapshots at the VBL entry; finding `d16(a4)` stores | what to snapshot: a compiled game's data hunk, or for an asm game whose variables sit at absolute addresses inside the code hunk, hunk 0. `d16(a4)` stores are the Aztec C form; an asm game needs an `abs.l` variant |
| `tools/compare_state.py` | compares the whole data hunk; a longword pointing into the code or data hunk at the same offset in both runs counts as equal, so builds that load the game elsewhere still compare | hunk sizes, `a4` bias. **A comparator written for one game's variable table reports "identical" on any other game.** Before trusting any compare, check that two runs of the same build compare equal and two different scenes do not |

Write `AGENTS.md`, and no `CLAUDE.md`, as in
[a project's agent instructions](../environment.md#a-projects-agent-instructions): the rules
from §0, a task-based index of the docs below and the path to the installed shared index.
Start the docs on this layout, each a current-state reference (§0):

| Doc | Holds |
|---|---|
| `docs/open-work.md` | where the work stands and the ordered next items; read first |
| `docs/development.md` | inputs and shared-file variables, build, run, driving, tracing, checks, measuring, release, traps |
| `docs/internals.md` | the program, display, game time, every slave patch, current measurements, known limitations |

Commit the scaffold.

## 4. First boot (windowed, real speed)

```sh
source amiga/env.sh
amiga/run.sh                       # windowed, sound; watch it reach the title and the demo
```

Size the machine from the slave header. WHDLoad needs base + exp + kick image (256 KB for 1.3)
+ itself + PRELOAD. **The A500-equivalent profiling machine** is 512 KB chip + slow RAM and no
fast RAM: `CHIP_KB=512 FAST_KB=0 SLOW_KB=1536`. Slow RAM is contended like chip, so every CPU
access stays on the chip bus as on a real A500. A literal 512+512 A500 is usually too small for
WHDLoad. Set the machine through the launcher's variables rather than `EXTRA_ARGS`: FS-UAE keeps
the first value of a repeated option and `EXTRA_ARGS` goes first, so a `--slow_memory` left there
(a `run.sh` default, say) silently overrides `SLOW_KB`.

Traps:
- `DOS-Error #223 (file is write protected)` looping on the kick file means the Kickstart copies
  are read-only. `run.sh` already does `chmod -R u+w`.
- The WHDLoad splash stays up while PRELOAD reads. That is not a hang.
- Each run has two logs, both under the run directory: `amiga/.run/fsuae.log` is the emulator's
  stdout and stderr (the shared launcher redirects them there), and FS-UAE's own log is
  `amiga/.run/fsuae/Cache/Logs/fs-uae.log.txt`, because the launcher passes
  `--base_dir=$PWD/.run/fsuae`. FS-UAE's log is block-buffered: read it after the emulator exits.
  `~/FS-UAE/Cache/Logs/` only collects runs that bypassed the shared launcher.
- Never repeat a WHDLoad option on its command line: a capture driver that adds `CUSTOM5` itself
  plus a user-supplied `CUSTOM5` stops the boot at an AmigaDOS argument error.

Watch the attract sequence and write down whether **the game plays itself** (a demo mode).
That decides how you drive it (§6).

**Check:** the game reaches gameplay under WHDLoad on the A500-equivalent machine.

## 5. Attach the debugger and get a trace with PCs in it

```sh
WARP=1 python3 tools/game.py serve > amiga/.run/serve.log 2>&1 &
python3 tools/game.py shot "$PWD/amiga/.run/now.png"     # 1-field trace → screenshot
python3 tools/game.py profile 10 "$PWD/tmp/prof/first.bin"
python3 tools/game.py quit
```

The stub's general behaviour (attach deadline, read-only memory, stopped emulated time, paths
with spaces, `until`, watchpoints, SR on older builds) is in
[the gdb stub](../reference/headless-fsuae.md#the-gdb-stub). What matters for WHDLoad traces:

- **Use the native build** (the `fs-uae` on `PATH`, `$FSUAE_ARM`). The shared server's
  `profile` sees it answer `monitor harness` and skips the lldb window fix. AmigaXDev's native builds profile the whole 24-bit space without a trigger, take keyboard,
  mouse and joystick input from gdb (`monitor key`, `mouse`, `input`) and run whole fields
  (`monitor fields`); see
  [harness commands](../reference/headless-fsuae.md#harness-commands-native-builds). The next
  two bullets are about the x86_64 build, which has none of that.
- **On the x86_64 build, without a trigger the profiler records no PCs.** The window
  `[baseText, +sizeText)` reads as `[0x0100007f, +0)`. The shared server's `profile` fixes it each time by lldb-writing `0`/`0x7fffffff` at
  link-time `0x32dea04` plus the slide. For a different FS-UAE binary, re-derive that address
  from the `GDBSERVER: enabled` setup and `start_cpu_profiler`. The
  assert fails loudly if it's wrong.
- **lldb can be slow to attach** to the x86_64 build: at ~40 s per attach, two attaches per
  capture (image list, then write) overrun a 60 s timeout. Use one attach that computes the slide
  and writes the window in lldb's Python, with a longer timeout.
- **Screenshots come only from traces** (`shot`). A failed `shot` replies `ERROR ...` and leaves
  no PNG, not the previous one; a route must stop on that reply or on a missing file, never
  reuse an image from an earlier step or run. macOS denies screen capture to this process,
  and posted host key events never reach FS-UAE (use `monitor key` instead). A shot taken at an
  arbitrary checkpoint (a keyboard task, a tape step) can catch a partial redraw: stop at the
  frame-publication instruction (§7) before saving a picture you will compare.
- At most **100 fields** per `monitor profile`, about 5.4 MB per field. For longer windows
  capture consecutive chunks and reduce each with `amigaxdev.callprofile` before deleting it:
  a 990-field route reduces to 3 MB in 25 s. The reduction rebuilds call stacks
  from JSR/BSR and the SP (the stub records none without a trigger) and timestamps marker PCs,
  with a running tally of wait-loop cycles, for per-frame costs.
- **One capture at a time per repo** ([sharing the machine](../reference/headless-fsuae.md#sharing-the-machine)).
- `run.sh` changes into `amiga/` before copying the slave, so resolve a relative `SLAVE` against
  the caller's directory first.
- The **68030 backend emits no instruction trace**. Count frames there with `SWAP_ONLY` (§7).
  The cycle-exact 68030/68040/68060 configurations have no validated instruction timing, and with
  `blitter_cycle_exact=false` their traces carry no blitter DMA records although the blitter runs.
  Report those routine and blitter costs as unavailable, never as zero, and never transfer A500
  percentages to them.
- **Tell supervisor and user code apart by which stack SP is in** when the build may report a
  stale SR.
- A trace taken with a profiler window set from the guest (a VERIFY-only `PROFILER_WINDOW`
  fixture) stores RAM PCs relative to the profiler start; keep that base in a `trace.pc-base`
  sidecar, which `amigaxdev.barto` honours. `until` should wait in the background with a timeout
  (`UNTIL_TIMEOUT`) and stop the capture cleanly, so a stalled route can still be dumped and quit.

**Check:** `barto.load()` on the trace shows instruction records **with PCs**, and the
screenshot shows the moment you expected.

## 6. Map memory, then find a reproducible gameplay window

**Regions.** Dump the "other" memory, where WHDLoad puts the slave's memory: `$C00000` slow RAM
with no fast RAM, `$200000` with fast RAM, and chip from address 0 on a machine with neither
(a stock A1200). Use `game.py gdb 'dump binary memory tmp/x.bin BASE END'`.
Adapt `regions()` until `game_report.py` names the code hunk, the data hunk, the kick image and
the slave. Relocations make an exact compare impossible, so 16-byte windows vote for a base.
Also, **the PRELOAD copy of the file is in memory too**: follow LoadSeg's BPTR chain from the
code hunk to the data hunk rather than byte-searching for it. For a direct game, look for the
code in base memory (chip, included in the trace's chip snapshot) *and* in the expansion memory,
which may be slow RAM on the A500-eq. and fast RAM elsewhere; the addresses move with the slave's
size and the memory configuration.

**Which slave copy is live.** Several slave-shaped copies sit in memory (PRELOAD, file). The live
one has its `resload` pointer filled in and some header bytes rewritten by WHDLoad, so match the
code after the pointer and require it to be non-zero. Trim the file to the hunk length first:
the trailing `HUNK_END` is not in memory. Anything the tools read *inside* the slave (a tape
counter, a marker) must be searched for from the live copy's start: with 8 MB of fast RAM a
marker can appear three times, the first being WHDLoad's file copy, frozen at 0.
And a byte-vote locator needs a quorum (a third of the windows, address ≥ dump base): DOS
buffers in chip RAM can hold pieces of the executable that outvote nothing and give a negative
"base".

**Driving.** Prefer the attract demo when there is one. Otherwise:
- **Keyboard-controllable games: `monitor key` on the native build**, no slave changes. Stop,
  then alternate `monitor key RAW 1|0` with `monitor fields N` (and `monitor profile` chunks in
  the window). With `WARP=1 DETERMINISTIC=1 JOY0=none` the route repeats exactly. Find the
  controls first: a game may start paused, need a key combination to select the keyboard, or
  move only on the keypad, not the cursor keys. Keep a joystick in port 1 if the
  slave reads a CD32 pad there: with nothing plugged in, its reader can see Play held and pause
  the game. Map each step with a contact sheet of `shot`s every few fields, then extend the route
  one move at a time.
- **Mouse and joystick games: `monitor mouse DX DY` and `monitor input EVENT 1|0`** the same
  way, for games that read the hardware, where Intuition's keyboard mouse (Amiga + cursor keys)
  does not move their pointer. Move in steps of at most 64 counts with a couple of fields
  between them; aim by screenshot, or close the loop on the game's pointer position (menus can be
  clicked through this way with `JOY0=none`).
- **Not** FS-UAE input recordings: in this FS-UAE build playback never works. FS-UAE emits two
  events of its own at startup (2263, 2272, whatever the ports are), and recording an event
  during playback truncates the recording at the play position, i.e. at 0. (Recording works;
  `KEY_RETURN` = 164 in this binary.)
- For an OS game, a **VERIFY input tape in the slave** (game independent): `_cb_dosLoadSeg` starts an Exec task whose TCB, stack and I/O live in the slave,
  counts fields with `WaitTOF` and types raw keys with `input.device` `IND_WRITEEVENT`. It
  publishes a marker and its field count so `fixed_window.sh` can poll it. Map the screens first
  (a `shot` at each tape step): menus, briefings and a manual check that a slave "removes" can
  each still wait for a key. The timing changes with the slave (an old slave vs KickEmu), so
  retime the tape when the boot changes.
  **Find out how the game consumes a key** before scripting gameplay: a game that takes one IDCMP
  character per frame, with a controller that turns one cursor character into full stick for
  one frame, turns with the *number* of presses, not with how long a key is held (a real
  keyboard's auto-repeat sends many). Hold each press longer than a frame, and wait until
  the gameplay loop is running (presses before it are lost).
- **Feed gameplay input inside the game's frame loop**, on frame numbers, once the game
  steps per frame: the VERIFY slave hooks the loop's call of its key reader and returns a
  scripted character on listed frames. Then every CPU and every run gets the same input on
  the same frames, the window (a frame number) shows the same scene everywhere, and game state
  can be compared across CPUs. Two weaker versions fail: keys typed at fixed fields land on
  different frames on a faster CPU (a different scene), and a task polling the frame counter
  once per field lets presses slip a frame when debugger stops shift the phase.
- For a gameplay window, script **some manoeuvring**. Straight and level flight over a
  flat-shaded sea changes 1 % of the view per frame, which flatters a delta c2p and under-loads
  the renderer. Agree the benchmark manoeuvre with the user (a turn, say).
- **Wait on game state, not on fields** (for example in a mouse game): screens arrive
  hundreds of fields apart from route to route, so fixed waits either misfire or waste minutes.
  A tape can write the pointer into the window's `MouseX/MouseY` and the buttons into the game's
  debounced state from its VBL server, and also hooks the game's button hit test to remember the
  list it was given: a `W` entry holds until that list has a given button id under the pointer,
  an `H` entry until the heading reaches a value, an `A` entry marks the anchor. Panels that poll
  through other code are invisible to such a wait: click them away
  blindly at intervals, and reject a window that starts inside one.
- For a direct game, hook the game's joystick read and feed it from a table indexed by
  field, selected by a `CUSTOMn` fixture option. Neither tape needs debugger writes.

**Reproducibility. This is the most important step; everything after depends on it.**
1. Find the game's sources of entropy: reads of `VHPOSR`/`VPOSR` (`$dff004/6`), CIA timers,
   `DateStamp`, uninitialised memory, **and input ports**. An RNG that mixes in VHPOSR makes the
   demo differ on every boot. Remove them in a **VERIFY build only**, gated by a `CUSTOMn`
   option. A game that reads the port-0 mouse counters (JOY0DAT) every frame sees a raw value
   that differs between boots. The host mouse feeds port 0 even with input grab off, so a mouse moving
   over the window injects input. Capture with nothing in port 0: **`joystick_port_0=none` is not
   enough in FS-UAE**: it unplugs the host device but the port's *mode* stays `mouse` (the
   default for port 0) and the host mouse still moves its counters. Also pass
   `--joystick_port_0_mode=nothing` (the shared launcher's `JOY0=none` does both). With that,
   two captures become identical in every register and DMA record. And people watching
   the emulator window can touch it: tell them, or treat a touched run as void.
2. Boot with `DETERMINISTIC=1`.
3. **Anchor on game state, not on wall time or screenshots.** Find a store that marks the start
   of play (a race-clock reset, say, followed by the gameplay loop). Arm it at CPU reset: `fixed_window.sh` boots once to learn the load
   address, caches it, and reboots with `BOOT_BREAK` armed so a warp boot can't run past it.
   Confirm with a gdb watchpoint. A simpler anchor: **the first execution
   since boot of the renderer's end-of-frame** (a swap request), if menus and credits don't use
   that renderer; it is first hit at the end of the demo's first frame.
   `SKIP_FRAMES=N` then gives later windows. **A breakpoint armed from reset makes warp slow**:
   a window ~4600 fields after boot was not reached with `BOOT_BREAK` in 5 minutes.
   With a tape, boot with no breakpoint, poll the tape's field counter (read-only; emulated time
   stops while gdb holds the CPU) and arm the anchor a few hundred fields before the last key. To find the start, step from the game's entry with
   counted VBL breakpoints and a `shot` every 100 fields. Traces of the transition show which code
   runs first.
4. Retain the exact slave with every capture (`OUT/slave.slave`), and analyse with
   `SLAVE=$OUT/slave.slave`. A different slave size moves the region bounds and can hide the
   frame marker.

**Check:** two fresh boots of the fixed window give byte-identical first- and last-field
screenshots and identical state snapshots. Stronger, and cheap: compare every field's instruction
records, DMA records and screenshot with `barto`; without the port-mode fix above, JOY0DAT can
read `$0000` in one boot and `$0101` in the other. Don't
`cmp` whole trace files: the slow-RAM snapshot holds WHDLoad/host bytes that differ between boots. Never compare two windows taken at arbitrary demo
moments: a demo can vary between 4.3 and 7.2 fps by scenery alone.

**Anchor on the game's frame counter, and hold the emulator while searching memory.** With
8 MB to dump and search, warp left running got thousands of fields past the arming point; and
a 0.2 s poll step in warp overshoots hundreds of fields. Open the window at a pass of frame N
by the game's own counter, which is deterministic whatever the poll did.

**Never edit a script while a capture is running it.** bash reads scripts as it executes, so an
edit to `fixed_window.sh` mid-run makes it execute garbage from a shifted offset (`h: command
not found` after 10 minutes). Copy the script, or edit only between runs.

**Memory, PRELOAD and blinking.** A disk-image slave without PRELOAD does a WHDLoad OS switch
for every disk read: the screen blinks through the boot and loads take longer, enough to break a
field-timed tape. Giving the slave 512 KB of fast memory (only DMA data in chip RAM) can leave no
room in 1.5 MB of slow RAM to preload three 880 KB images; a 68000 + 512 KB chip + 8 MB Zorro II
fast capture machine fits both (the user's call). KickEmu's `IOCACHE` only caches `HDINIT` files, not
disk images.

## 7. A frame counter you can trust

Find the instruction that makes a new frame visible:
- a COP1LC write (the slave's own copper patch, `move.l a0,$dff080`, or the game's VBL handler
  where it runs only when the renderer has set a swap-request bit);
- `BPLxPT` writes in a copper list;
- `LoadView`/`ScrollVPort`;
- a double-buffer flag flip;
- or, with **one displayed buffer**, the pass that writes it. A game that renders chunky and
  converts with a delta c2p straight into the visible bitplanes counts frames at the c2p entry.
  Check the destination planes across frames before assuming double buffering.

A VBL handler that rewrites the bitplane pointers every field is not a frame counter by itself:
if it writes `BPLxPT` on every VBL and publishes a new frame only through a conditional buffer
exchange, the exchange is the marker. Where the trace is empty (68030 and up), a
read-only watch of the front-buffer pointer at successive VBLs counts the exchanges; check first
that it reproduces the swap breakpoints on the 68000 and 68020. Where you can, confirm the
marker against the display: the COP1LC or pointer write must be followed by bitplane DMA from the
new buffer in the next field.

The level-3 vector may not be the Kickstart's: a game can install its own sound handler there and
chain to the ROM handler past its prologue. Count level-3 entries at whatever `$6C` holds.

Count those per PAL field. Over 100 fields that gives `fields/frame` and fps. Write it into
`frames.py`, and as read-only breakpoints into `swap_fields.py` for CPUs whose trace is empty.

Also find how the swap is timed: a beam wait, `WaitTOF`, or a VBL handshake. Count the CPU's
swap-wait spin separately from blitter waits (it can be 2.5% of an A500 frame and 10.5% on a
68020). And find every blitter-wait idiom, not just `btst #6,2(a6)`: absolute
`btst #6,$dff002` and register forms like `btst d4,(a6)` with `a6=$dff002`, which can be the
hottest. A slave that waits for a VPOS line before the swap quantises frames to whole fields and
caps the rate at 25 fps; such a wait is usually a flicker fix: **don't touch** it without testing
a fast CPU for tearing.

**Check:** `SWAP_ONLY` and the full trace give the identical swap pattern on the same window.

## 8. Baseline profile

Run on the A500-equivalent machine, in the fixed window:

```sh
tools/fixed_window.sh tmp/prof/base
python3 tools/game_report.py tmp/prof/base/trace.bin tmp/prof/base/code.bin --base 0xc00000
python3 tools/frames.py     tmp/prof/base/trace.bin tmp/prof/base/code.bin 0xc00000
python3 -m amigaxdev.disasm hotspots --label game tmp/prof/base/trace.bin tmp/prof/base/code.bin 0xc00000 <hunk> <off,...>
python3 -m amigaxdev.disasm disd tmp/prof/base/code.bin 0xc00000 <hunk> <start> <end>
```

Record, in `docs/internals.md` (current measurements) with the command in `docs/development.md`:
- fps;
- CPU share per routine, both inclusive (call tree) and self;
- blitter-wait cycles (`btst #6,2(a6)` or `btst #14,dmaconr` polls);
- interrupt counts and cost per handler;
- DMA slot shares (free / CPU / blitter / bitplane / copper);
- whether the CPU ever idles (`STOP`).

Attribution needs care:
- **Self time** goes to the nearest preceding function start: compiler prologues
  (`link a5` for Aztec C, `link a6`/`movem` for SAS/C and others) plus every observed call
  target. **Hand-written asm games have no prologues**, so check big self numbers with
  `amigaxdev.disasm hotspots`.
- **Contexts** come from SP ranges: an OS game may have a main task, a second game task, OS
  device tasks and the supervisor stack. A direct game may run everything, interrupts included, on
  one supervisor stack. Then interrupt work shows up as "calls" from whatever it interrupted (a
  SOFT handler "under" two unrelated routines). Identify handlers from the vectors at
  `$64..$78` in the chip snapshot and count their entries instead.
- **Asm with absolute addressing**: take function starts from every static `jsr abs.l` and
  `bsr` target in the code hunk (after relocation), plus the traced call targets.
- `jsr d16(a6)` is named after the library at `a6` plus the LVO.

Then repeat the trace on a 68020 with fast RAM, to see what is bus-bound and what is CPU-bound:

```sh
AMIGA_MODEL=A1200 KICKSTART=$KICKSTART_A1200 CHIP_KB=2048 FAST_KB=4096 \
  CPU=68EC020 SLOW_KB=0 tools/fixed_window.sh tmp/prof/a1200
# 68030 at N Hz (no instruction trace; use SWAP_ONLY=1, and SERVE_WAIT=1700 above ~100 MHz):
CPU=68030 SLOW_KB=0 EXTRA_ARGS='--uae_cpu_speed=real --uae_cpu_multiplier=0 --uae_cpu_frequency=25000000 --uae_cpu_cycle_exact=true'
```

Use `--base 0x200000` for fast-RAM dumps.

**The machine matrix.** One set, all running the same build and window:
the A500-equivalent (68000, 512 KB chip + 1.5 MB slow, `AMIGA_SETUP=a500-1.5m`); a stock A1200 (68EC020, 2 MB chip, no
fast RAM), which can behave differently from an A1200 with fast RAM; an A1200 with 4–8 MB
fast; a cycle-exact 68030/50 with and without WHDLoad's `MMU` option, whose out-of-box cache states
differ; and a 68040/25 and 68060/50 as `-NOMMU` (below). Add NTSC cells only when the
game supports NTSC (§9). Script the matrix to run one capture at a time and give each boot a
deadline, so a hung cell fails instead of blocking the queue.

**Find the ceiling before choosing work.** On the fastest configuration, build a
matched control and a bypass with identical size, placement and alignment that differ only in two
bytes (`rts` at, say, the polygon filler's entry), and also run the control with an instant
blitter. If the control draws 38.5 fps, instant blits 44.2 and no polygons 49.9, there is no
publication cap, and a material blitter and bus share. Use the matched control as the reference,
not the regular build, whose different layout changes the timing. The two gains don't add, and
the bypass is not a visual test. Read the DMA slot shares beside the blitter-wait cycles: 30% of a
68020 frame in blitter waits with half the chip-bus slots free means the cost is the latency of
many small serial blits, not bandwidth.

**68040/68060 in FS-UAE.** Use `CPU=68040-NOMMU` (likewise for the 060) with the cycle-exact
68030 options and the frequency changed. With plain `68040` FS-UAE emulates the MMU, WHDLoad
turns it on, and the MMU loop then ignores the frequency and the chip timing. The generic loop
(`cycle_exact=false`, `cpu_compatible=false`) ignores them as well. Even the cycle-exact
040/060 loop is close to an instruction count, about 14 million instructions per second at any
configured clock ([measurement method §3](../reference/measurement-method.md#3-instruments)): equal
frame rates at different 040/060 clocks say nothing about the game, and only a real accelerator
gives a hardware frame rate.
`cpu_speed=max` is not a real machine: chip accesses are nearly free there, and so is an
instant blitter, so neither is a ceiling for real hardware.
Run a separate functional boot with the MMU on (`CPU=68040`, `68060`); its timing is not
comparable to the fixed-clock runs. Do not assume that the MMU core has no cache behavior:
the pinned native builds include the [MMU write-attribute correction](../reference/headless-fsuae.md#cached-040060-mmu-write-attributes).
A scoped 68040 fixture also demonstrates copyback data retained
in cache while raw debugger reads still show old RAM; see the
[cache observer and its validated limits](../reference/cache-observer.md). Record the build,
CPU, MMU and actual cache state. A successful boot alone proves neither cache coherency nor
hardware timing, and the 68040 observer result does not validate every CPU model.
Real-hardware cache failures are in [Hardware debugging](new-game-playbook-hardware.md).

**Caches on fast CPUs.** Without an MMU (a 68020, or a 68030 without WHDLoad's `MMU` option)
WHDLoad keeps the caches off, and many old slaves switch them off themselves. Know which state a
68020/68030 figure was taken in before comparing it (a slave can define KickEmu's `CACHE`).
A slave that marks BaseMem non-cacheable (`WCPUF_Base_NC`)
can make WHDLoad turn every cache off without the MMU, so 68020/68030 numbers taken that way
are uncached. Do not infer the live state of another CPU or loader from this policy request:
a CACR audit has observed instruction caching enabled on 68040/060 NOMMU configurations, with
data caching disabled, despite a non-cacheable BaseMem request.
Measure with WHDLoad's `DCACHE` (or `CACHE`) when the slave leaves caches alone.
Whether the slave manages caches is a per-game decision for the user: leave them to WHDLoad's
options (with the ReadMe recommending `DCache`), or enable KickEmu's `CACHE`.

Record the cache state behind every figure from the hardware, not from the API. A VERIFY-only
boot can log `CACR` right after the slave's `resload_SetCPU`; the API state
reports instruction and data caches requested even on CPUs that have neither. Read `CACR` only
on a 68020 or later (the 68000 has none, so never execute `MOVEC` there), and keep the audit out
of the normal build: `resload_Log` needs WHDLoad 18. When KickEmu's non-cacheable BaseMem has
turned every cache off without the MMU, enabling only the instruction cache through
`resload_SetCPU`, leaving the data cache as WHDLoad set it and respecting `NoCache`, gained 10% on
a 68020 and 7% on a 68030 without the `MMU` option in one game. Like any cache policy in the
slave, that is the user's decision; a user may reject a slave that enables caches itself.

For hardware-only black screens, stale executable stubs and WHDLoad dump analysis, see
[Hardware debugging](new-game-playbook-hardware.md).

## 9. Understand game time before optimising anything

For a fixed-step replacement, also read [fixed-time simulation](fixed-time-simulation.md):
completed-tick versus elapsed-field checks, historical input, native pauses and control feel.

This is where most of the effort belongs. A faster renderer is
worthless if it also speeds the game up, and pointless if the simulation only moves things
8 times a second. Answer these with measurements:

1. **Time sources.** Which does the game read? VBL counters, CIA timers, `timer.device`,
   frame-count deltas, or nothing (a fixed step per rendered frame)? Grep the binary for
   `$dff004/6`, `$bfe801/$bfd800`, `$6C` vector installs and OS calls, and confirm with traces.
   Also grep **every** CIA timer register (`$bfe401..$bfe701`, `$bfd400..$bfd700`, CRA/CRB, ICR),
   in the loader/intro too: the game's code may never program its clock because the intro sets a
   CIA timer (say CIA-A timer B at 59.7 Hz) that the game divides into a SOFT (level-1) interrupt.
   A tick-driven main loop **caps the frame rate at the tick rate** (15.2 fps on a 25 MHz 68030
   against a 14.9 Hz tick). Run the fast-CPU `SWAP_ONLY` early, because it shows the ceiling.
   **Check the clock's rate against emulated time.** A timer that the sound code also programs
   can run the game at the wrong speed: a sound driver that reloads a shared CIA-B latch can make
   a 10 Hz simulation take 8.3 steps/s on the A500, so game time runs 17% slow.
   Measure steps per second and game clock against emulated time on every machine first.
2. **The state map.** Find the variables that *are* the game: position, speed, clock, opponent
   state, RNG, lives, and so on. Locate them by watchpoints on what changes on screen, then
   `state_writers.py`. Snapshot the data hunk every field at the VBL entry (`STATE_FIELDS=N`) and
   compare with `compare_state.py` (§3).
3. **The coupling test.** Run the same fixed window on a 68000, a 68020 with fast RAM, and with
   deliberately slowed drawing (a VERIFY-only delay in the draw path, behind a `CUSTOMn`). Compare
   state field-by-field with `compare_state.py`. Identical state at different fps means the
   simulation is already decoupled. Divergence tells you exactly where it is coupled.
   In a coupled game a field-indexed input tape feeds different inputs per simulation step once
   drawing slows, so the slowed run legitimately reaches a different scene (a slowed driving tape
   can crash where the normal one jumps): compare per step, with the input each step
   consumed, not the same scene at the same field. Keep the slow-drawing instrument from
   disturbing what it measures: count VBL transitions in the handler and wait N of them before
   the frame is marked ready, with no `STOP`, host sleep or state writes; preserve the flags the
   displaced instruction sets; and install nothing when the option is 0.
4. **Tasks and interrupts.** Which context advances the simulation? A game can have a separate
   simulation task (8.33 Hz, say), plus drawing that shares the RNG. Use SP ranges and per-task
   state snapshots.
5. **Boot benchmarks.** The time step may come from a benchmark at boot rather than a clock. A
   game that draws a test scene, sets `T = 380 / fields taken`, and advances `1/T` s of game time
   per frame has the right game speed only at the frame rate the benchmark predicted (an A500 can
   run 1.9× real time, a 68030/50 0.55×). Check what else reads that value (detail levels, menus)
   before changing it: a per-frame T can replace it in the main loop while the boot value stays.
   Smooth a per-frame T. T from the last frame alone alternates with uneven frame lengths (25 and
   17), so intervals the game counts in multiples of T (a gun's reload T/3, a bullet's life 2T)
   jitter between 12 and 20 fields. T from the average frame length, with the time owed carried,
   gives 14–18 fields at unchanged game speed. Large T also exposes truncation: carry 16.16
   fractions in step lengths and turn rates, or speeds fall short of nominal (4,649 instead of
   4,712 units/s).
6. **PAL and NTSC.** Find out whether anything assumes 50 fields per second. To detect the rate,
   take the beam's highest line over a field (PAL 312, NTSC 262; threshold 288), reading
   `VPOSR`/`VHPOSR` twice so a read across line 255/256 isn't taken as a wrap.
   NTSC runs need FS-UAE's core option `uae_ntsc=true`: the frontend's `ntsc_mode=1` alone leaves
   this build in PAL timing, so "60 Hz" results taken that way are PAL. The shared launcher's
   `NTSC=1` passes both. GLib queue warnings appear in successful PAL and NTSC runs alike and are
   not a stall. Have the capture driver compare the mode it asked for with the measured field
   rate (the beam's highest line, or Exec's) and fail on a mismatch.

**Raising a tick-capped frame rate**: remove the main loop's tick wait, snapshot the
published state (camera, car poses) at the simulation tick's common exit, and rewrite only the
renderer's copies each frame with α = time since that exit / tick period. Interpolation
(`prev + (cur − prev) × α`) is smooth but shows the scene one tick late; extrapolation
(`cur + (cur − prev) × α`) removes that delay but overshoots at sudden changes. Snap at cuts and
teleports, wrap track coordinates and take angles by the shortest arc. Input sampling and the
simulation stay at the tick rate. **Validate on real gameplay, not only the demo:** a cockpit
view can prepare its camera on a different path from the demo cameras, so demo-only checks miss
that interpolation never runs while driving. Add a test build that drives the native menus with
a held input and check frames within one tick actually move.

**Choosing a simulation rate.** Price the tick on the A500 first: a finer fixed tick multiplies
the simulation cost, and on a 68000 it can leave nothing for drawing. A native update costing
about 90k cycles of the 97k available per NTSC field presents 0.4 fps with 60 Hz substeps, and
taking a tick from 137k to 90k cycles against a 40k target is a structural gap no tuning closes.
A finer world quantum can need 101% of an A500 in a busy scene; a 25 Hz tick can drop an A500
from 3.3 to 1.2 fps. What works: keep the native step on the 68000 and use a finer step only
where it measures affordable (a per-CPU tick period, or a finer quantum on 68020+), chosen once at
start and never changed mid-game. Decide with a measured matrix, not a cost model: a model that
predicts 3–4 fps at 15–20 Hz can still leave only the native rate meeting the A500 gates. If the
steps per native update become a build constant, the native-rate build must stay byte-identical,
every constant derived from the step count must be found (grep the patch sources, fixtures and
checkers for the old literals), and states at native boundaries are compared across step counts
with every divergence classified. Interpolate only where frames are shorter than a tick: on the
68000, present the latest state and skip pose capture and blending.

**Acceptance for game speed** (once whole-state identity across CPUs proves unreachable and
unnecessary): at equal wall time, completed world time is within ±1% of nominal
for every render schedule (normal, deliberately slowed, one field) whenever the world cost fits
the CPU; the number of funded ticks never depends on render time; one-shot commands run exactly
once and held controls apply to every catch-up tick; pause, menus and preferences rebase the clock
without catch-up; and with the option off the original bytes remain. Bound the debt (1 s of world
time, say) and count dropped time in VERIFY. Record the residual state differences between
quanta or CPUs instead of demanding byte identity, and leave the feel to the user's play-test.

See [simulation and presentation](simulation-and-presentation.md) for replay-specific
snapshots, native-rate prediction, load-address controls in state comparisons, and the
units/precision audit needed before reducing the simulation timestep.

A slowed renderer is easy to get when you are testing a replacement anyway: a slower c2p
experiment (8.7 instead of ~5 fields a frame) plus a state comparison at an equal frame number
is the coupling test (`STATE_ONLY=1` + `compare_state.py`). Compare
before the first scripted input, or the input lands on different frames.

Write the verdict, evidence and possible designs in local `docs/open-work.md`. Follow the
user’s authorized scope; ask for a choice when designs materially change gameplay or intent.
Routine setup and validation can continue while a design decision is pending.

### Before replacing a c2p, measure the change rate

A *delta* c2p (compare with the previous chunky frame, convert only changed longs) wins when
little changes. In a flight game 1 % of the view can change in level flight and up to 13 % in a
roll; with a compare at 31 cycles per long and a conversion at 382 per changed long, a full-frame
merge c2p in Kalms' style cost 634,000 cycles per frame against 117,000 and dropped the A500 from
9.7 to 5.7 fps. Kalms' routines take a byte per pixel; for nibble-packed chunky, search the
exchange plan (six steps for one nibble order) and check the assembly against the game's routine
in an interpreter before booting.

## 10. Building and gating patches

- Cross-build the slave with vasm (a small `whdload/makefile`):
  `-m68000 -pic -x -devpac -Fhunkexe -nosym -I$(WHDLOAD)/Include -I$(NDK)`. Build on the shared 20.1
  KickEmu and headers (vendored), but **declare `slv_Version = 17`** and no `slv_MemConfig` unless
  the slave really needs a v20 feature: `kick13.s` handles both through `IFGE slv_Version-20`.
  Use the single shared `WHDLoad/` development tree; old versioned paths are retired
  without aliases. Test a stated older runtime minimum with an explicitly
  supplied runtime binary via `WHDLOAD_BINARY`; setup maintains only the latest developer kit.
- **Test paths containing spaces at both make and shell levels.** Quoting `-o "$@"` is
  insufficient if make has already split `$(OUT)/Game.Slave` into separate targets. Escape
  spaces in the target/prerequisite spelling, and separately quote assembler, listing and
  output arguments in the recipe. Exercise release, developer, VERIFY and clean targets with
  absolute and relative spaced `OUT` paths, and compare the resulting release bytes against the
  ordinary-path build.
- **First rebuild the unmodified slave** and confirm it boots and gives the same fixed-window
  state as the shipped one. The bytes will differ (BASM date stamps, a vendored kickemu;
  vasm writes `cmpi.w #imm,Dn` as `cmp.w` even with `-no-opt`, and pads with `nop` where ASM-One
  left junk), so confirm by behaviour.
- Vendor the kickemu sources the slave includes into `whdload/whdload/`.
- Gate every change behind a `CUSTOMn` bit and declare it in `slv_config`. With the bit off, the
  original bytes must be untouched. Write a checker that reads the local original file and
  compares those bytes at every patched range (`check_disabled.py`).
- **Compare the rebuilt slave with the shipped one by behaviour, and state what was compared.**
  A rebuild on the WHDLoad 20 KickEmu changes allocation and OS timing (a 68000 sequence can take
  387 fields instead of 195), so measure performance only with the same loader on both sides.
  Compare the sequences of distinct sampled poses and stable screen images (functional
  equivalence, not per-field equality), or compare the game bytes after undoing relocations, the main state block with named exceptions (RNG seed, clock samples)
  and both bitmaps outside the on-screen clock, with negative checks proving the comparator fails
  on any other byte.
- Keep instruments (fixtures, RNG pinning, slow drawing, pixel twins, assembly unit tests) in a
  **`VERIFY` build only**. Normal builds must not contain them.
- Audit hook boundaries: a `PL_PS`/`PL_PSS` must replace whole instructions, and nothing may
  branch into the replaced bytes (a hook audit script). One wrong return adjustment can land two
  bytes early and crash much later; a sentinel unit test catches it.
- Choose the patch type deliberately. Use `PL_P` (jump, no return) when the replacement
  re-executes the original body: a `PL_PS` twin returns into code that has already run and
  corrupts the stack.
- **Find self-modifying code before moving or caching code.** Decode the executed instructions
  of a capture, evaluate each write's destination from the recorded registers (indexed and
  register-indirect as well as absolute) and intersect the written bytes with executed
  instruction bytes. A rasterizer can rewrite branch displacements; data words inside a code hunk
  are not self-modifying code. Replace such writers with static specialised loops and a dispatcher
  that keeps the continuation in data, so drawing never writes code. Build generated code before the slave's final `resload_Patch` flush, or flush after
  it ([Hardware debugging](new-game-playbook-hardware.md)), and leave cache selection to
  WHDLoad's `CACHE`/`DCACHE` options.
- Reading `SR` is privileged on the 68010 and later. A hook that may run in user mode saves the
  condition codes with `MOVE CCR` there (it doesn't exist on the 68000).
- **Give the game the entry registers its contract promises.** A loader that jumps into the
  DOS program with the `a0`/`d0` that `resload_Patch` may destroy lets the game dereference them
  as its command line, which only an MMU boot may expose. Pass a valid empty command line (`a0` → a
  newline, `d0` = 0).
- Gate per-CPU behaviour on `WHDLTAG_ATTNFLAGS_GET`, read before `resload_PatchSeg`, or on
  exec's `AttnFlags`. A slave can ship a 68000 and a 68020 version of each maths routine
  (`mulu.l`/`divu.l` where the original paired 16×16 operations give identical bits) and pick one
  at patch time; assemble them in `MACHINE 68020`/`68000` sections.
- **Gate on memory too, and measure the slow machines.** A feature that helps a fast CPU can
  slow a chip-only machine: CPU drawing can cost 10–20% on the A500 and 5–15% on a stock
  A1200. Make such an option work only on a 68020+ with the code hunk in fast RAM (not chip below
  `$200000`, not slow RAM at `$C00000–$DFFFFF`), so the A500 and stock A1200 run exactly
  the original. Prefer one player-facing toggle and keep manual values for tooling unlisted.
  Whether it defaults on is the user's call. Default on, with the original game one switch away,
  suits a set of changes (faster rendering, frame pacing and real-time simulation) that only
  behave as intended together.
- **Check what spills into chip RAM when the expansion pool fills.** A 512 KB ExpMem with
  24 bytes free sends the game's `MEMF_ANY` blocks to chip. A VERIFY-only census through the
  KickEmu `AllocMem` vector listed every spilled block; once no DMA was found touching them,
  raising the slave's fast-memory size to the measured peak plus headroom gained 4–13% on the
  68020 to 68060. Check that the minimum A500 configuration still boots, update the ReadMe's
  memory line, and keep DMA data in chip.
- **CPU-only buffers can use `MEMF_PUBLIC` without requiring fast RAM.** Audit every reader
  and writer for DMA use first; bitplanes, audio and blitter-visible buffers have different
  requirements. Let Exec choose eligible memory, retain allocation-failure behavior, and pair
  ownership with the matching free routine and size. Do not infer physical fast RAM merely
  from an Exec FAST flag: distinguish expansion slow RAM from uncontended fast RAM in profiles.
  Move only the CPU-only allocation (a chunky buffer, say), not a whole pool.
- **Follow DMA addresses through image descriptors.** A header read only by the CPU can still
  determine a DMA source: native code may add a pixel offset to the header's own address.
  Moving that header then redirects the blitter even if the pixel data stayed in Chip RAM.
  The symptom is coloured rectangles after relocation, possibly only on a separate bootstrap
  loading image once the other screens are fixed. Trace the final hardware pointer through
  header decoding and base-plus-offset arithmetic. Keep inseparable descriptor/pixel blocks
  in Chip RAM, or explicitly preserve their pixel base when relocating the descriptor.
  Check loading, intro, menus and gameplay independently; their formats and owners can differ.
- **Draw in fast RAM, copy to chip** on a 68020+ with real fast RAM: copy the
  rasterizer into fast RAM along with a staging bitmap, draw the scene there, then wait for the
  display handshake immediately before a `MOVEM` copy of the drawn rows into the chip back buffer,
  so the wait overlaps fast-RAM drawing. The code fetch can be the win: the bitmap alone gained
  nothing on a 68020 where bitmap and code took it from 15.7 to 22.2 fps, a 68040/25 from 17.9 to
  41.2 and a 68060/50 from 17.9 to 42.7. A 68000 with fast RAM was 17% slower, so gate it by CPU.
  Require real fast RAM (`TypeOfMem`; reject WHDLoad expansion backed by slow RAM at `$C00000`)
  and fall back to native drawing otherwise. The extra expansion memory raises the slave's
  requirement even with the option off. Twin it as below, and also poison the staging areas the
  scene must not touch, guard both ends of every buffer, and compare raw registers before
  translating relocated pointers.
- **AGA fetch mode.** On AGA a slave can switch bitplane DMA to 64-bit fetch (`FMODE` = 3) when
  the game's bitplanes and modulos meet the 64-bit alignment, freeing chip-bus slots for the CPU
  and blitter ([the Chip bus](../reference/amiga-hardware.md#the-chip-bus)). JOTD's Fighter Bomber
  and Killing Cloud slaves do it on AGA only, with a `DDFSTOP` of `$b8` for the wider fetch:
  Fighter Bomber measured 4.53 → 4.98 fps, and Killing Cloud keeps an option to leave the fetch
  mode alone. Other games measure no gain or show a corrupted display. Treat it as
  an option-gated candidate: check the picture, and expect most from games with five or more
  lores planes whose CPU or blitter waits on chip RAM.
- **Pixel twins for renderer replacements**: the VERIFY build runs the
  new code into a guarded shadow bitmap, then the native code into the real one, and compares
  every plane plus the registers that survive, including X. Twin the replaced inner loop, not the
  whole function: callers may enter partway with their own state (a dither phase). The stub
  ignores memory writes, so select fixtures at boot with `CUSTOMn`, never through gdb. A
  framebuffer twin cannot show a display-fetch problem: check those on screen.
- **Check every replaced routine against a model of the original, in the emulator**: write a Python model of the original routine and check it
  against the original's own calls first; then, in the VERIFY build's fixed window, break at the
  replacement's entry and exit for N calls, dump inputs and outputs, and compare with the model.
  Do it on the A500-eq (68000 code) and a 68020 (68020 code). Include the edge cases the model
  shows (negative operands in sign-magnitude maths). This is cheaper and stronger than state
  comparisons, which only show that a scene looks the same.
- **Declare every hook range where it is installed** (a `PERF_RANGE hN:OFFSET LEN bit=B`
  comment beside each patch), so the disabled-bytes checker reads its list from the source and
  can't drift from it.
- **Keep the original code on a CPU where the replacement doesn't measure better.** Unrolled
  loops and lookup caches that help the 68000 can regress or do nothing on the 68020; then
  68020+ keep the original bytes; VERIFY can still force each body on either CPU for
  its twin. A release build may force all verified performance bits on and expose only the
  player-facing options, while a `DEVELOPER` build keeps the individual switches for A/B work.
- **Kalms c2p** (shared checkout `~/.local/share/amiga/kalms-c2p`; vendor the files you use with
  a README listing every local change): for 16 colours, `bitmap/c2p1x1_4_c5_bm_word.s` on
  68000/10 and `bitmap/c2p1x1_4_c5_bm.s` on 68020+. They need widths that are multiples of 32.
  For narrower views convert an **enclosing window** from a staging buffer padded with colour 0,
  and save and restore the extra destination bytes around the conversion: after a view switch
  they can still hold the previous view's pixels (a pixel twin catches this). Make
  the pixel twin perturb the bits the game leaves undefined (an unused nibble), so a wrong merge
  can't hide.

### Allocate runtime buffers instead of embedding zeroes in the slave

Keep large recording arrays, snapshots and scratch buffers out of the slave file.
A zero-filled `dcb` in the code section is still file-backed storage; compression
in the release archive does not fix the installed file. Keep small control fields
and pointers in the slave, and allocate bulk storage for its actual lifetime.
WHDLoad's `SlaveOverview` in `$WHDLOAD/Docs/autodoc.html` requires a single hunk
and entirely PC-relative code without relocations: a separate BSS hunk is not an
alternative for the slave. This restriction does not apply to the game's executable.

For a KickEmu slave, use the emulated Exec `AllocMem` while that environment is
available, before installing hooks that use the buffers. CPU-only data can use
`MEMF_PUBLIC|MEMF_CLEAR`; DMA buffers need the appropriate Chip RAM allocation.
Allocate only for the supported game/option, check failure before publishing
pointers, and report a clear error rather than continuing with a null pointer.
Make repeated initialization reuse or explicitly release the allocation. For a
whole-session allocation inside KickEmu's reserved pool, WHDLoad reclaims the pool
on exit; shorter-lived allocations need matching `FreeMem` calls. A direct slave
without Exec must instead partition memory reserved through its WHDLoad header;
do not assume the host's Exec allocator remains available after takeover.

**Budget the destination pool.** Moving storage out of the slave does not remove
its runtime RAM requirement. Increase the relevant reserved pool if needed so the
buffers do not steal the game's previous headroom; account for alignment, allocator
overhead, ROM storage and peak game allocations. Update the documented requirements.
One cleared block (129,556 bytes for recording arrays and two snapshots, with an extra
128 KiB in `FASTMEMSIZE`) took one slave from 153,300 to 23,888 bytes; these are file
sizes, not a performance measurement.

Check the allocator request, pointer layout, disabled-option path, repeated calls
and failure handling. Update fixtures to dereference buffer pointers rather than
assuming that a symbol is the buffer. Run the affected recording/snapshot/file-I/O
checks, then boot a real KickEmu session and exercise the feature: a CPU harness
with a stubbed allocator cannot establish that the real memory pool is sufficient.
Physical-machine validation remains separate.

## 11. Measuring an improvement

- A/B **only** with `fixed_window.sh`, same build, the option on vs off. The fps figures come
  from swap counts. Script the whole pair (`ab_window.sh PREFIX OFF ON [ROUTES [MACHINES]]`:
  both machines, both routes, one capture at a time, then the analysis chain on each capture;
  a summary script tabulates them and writes off/on first/last comparison sheets). Delete each 0.5–1 GB trace once its reports exist (`KEEP_TRACE=0`): a
  deterministic window can be recaptured.
- When game time depends on frame time, the faster build reaches the anchor in a different
  scene. Quote fps, but judge the routine by **cycles per completed call** (boundary-partial calls
  excluded, main task separated from interrupts), and add a scene-stable route (stop facing
  a wall, wait, then anchor). Physics and state correctness come from per-field state comparisons, never
  from screenshots.
- Skip anything worth under 3% of a frame unless it's free. Bound a candidate's cost by summing
  its instructions' cycles before writing it. An fps window cannot even resolve the sign of a
  change under about 2%: bound such changes statically, and drop any step that
  measures under 2% on every CPU class once implemented.
- Re-run the fast-CPU configurations. A change can help the A500 and do nothing on a chip-bus
  bound 68030, or the reverse. A renderer can hit a 25 fps chip-bus ceiling at any CPU speed.
- **A faster CPU does not make chip RAM faster.** On AGA the CPU's 32-bit chip stores beat the
  16-bit blitter for fills (no reads), but the blitter wins chip-to-chip copies (textured rows
  by CPU dropped one heavy view from 24.0 to 20.4 fps). A cached 68030 at 200 MHz can still draw
  12 fps. Equal 040/060 figures at different clocks (the same fps at 25 and 40 MHz, or between a
  68040/25 and a 68060/50) are FS-UAE's instruction-count timing (§8), not evidence of a chip-bus
  bound.
- **Blitter priority (`BLTPRI`) helps when the CPU polls the blitter.** Set it while the game
  runs and restore it on exit, so the CPU's `DMACONR` polls stop taking blitter slots: one game
  measured A500 5.2 → 5.4, A1200 16.1 → 16.7, 68020/100 21.1 → 25.0 fps; another measured no
  effect. It disturbs the 68020 cycle trace: use `SWAP_ONLY` for fps when it is on.
- **Spend measurement on decisions.** An agent can make 209 commits in three days where the last
  132 do not change the player build and 81 of the last 100 are verification or measurement.
  Give each feature a fixed budget: build
  every mode; run the host tests and the hook audit; one same-build A/B window per affected CPU
  class (≥2,000 fields, or 1,000 of steady play on the A500); one native twin for an exact-output
  replacement; two or three deliberate sabotages for any new checker. Run the full machine matrix
  only at checkpoints, never rerun the emulator without a source change in between, and open a
  work item only for a demonstrated defect.

## 12. "Ready to improve": the definition of done for setup

- [ ] Rules, a doc index and the shared index path in `AGENTS.md` (no `CLAUDE.md`); `tmp/` ignored; no game bytes in git (`git ls-files` reviewed).
- [ ] Game, version, slave type and existing patches documented.
- [ ] `game_report.py` names every hot region; traces have PCs.
- [ ] A fixed gameplay window that is reproducible across boots: same screenshots, same state.
- [ ] A validated frame counter: full trace and `SWAP_ONLY` agree.
- [ ] A baseline on the machine matrix (§8), with a profile on at least the A500-equivalent and a
      68020, each machine's cache state, and the commands that reproduce it.
- [ ] No local paths in the tree (§0 grep); shared files through the §1 variables.
- [ ] The game-time model: time sources, state map, coupling test results.
- [ ] `docs/open-work.md` lists the ordered work items and the decision the user must make.
- [ ] A rebuilt, unmodified slave that behaves identically, with CUSTOM gating and a VERIFY
      build ready to receive patches.


## 13. Release archives

When the work ships, add `make dist` (a packaging script): for each original archive
(installer pack and Retroplay pack, kept in `tmp/`), unpack it, replace the slave, the ReadMe
and any slave source the original ships, and repack to `dist/` (ignored).

- **The release has the previous release's files.** If it shipped no slave source, add none.
  If it shipped source (`source/`, `Source/`, `src/`, with or without a `Makefile`), replace it
  in that directory with the current release source, keeping the shipped names where the files
  still exist. Add exactly the files the release build of the main source includes, so the
  shipped source assembles to the shipped slave, and drop shipped source files that no longer
  exist (a superseded `.asm`). Never add docs, notes, VERIFY-only modules, extra makefiles or
  copies of SDK includes (`whdload.i`, `lvo/`, kick sources). Find the included set from the
  assembler's dependency list (`vasm -depend=list`) of the release build, and prove it by
  assembling the extracted archive's source against the installed SDK.

- **Lhasa can't create archives.** Use LHa for UNIX (`LHA`, §1) with level-1 headers
  (`lha a1o5q2`, matching the originals). An alternative for a strict two-file update is a
  record-level rewriter: retain each unchanged compressed record verbatim and emit standard
  stored `-lh0-` records for the replaced files. This needs no compressor and preserves
  untouched metadata, but produces larger replacements. Its parser supports the known
  level-0/1 inputs only; reject unsupported headers rather than guessing boundaries.
- Stage a fresh extraction of each original archive under ignored `tmp/`, not a game drawer
  used for emulator runs: that drawer can contain saves, changed preferences or `.uaem` files.
- Keep exactly the original member list and names (including case, `Game.Slave` vs
  `Game.slave`). Compare sorted lists: LHa for UNIX sorts members, so original order is not preserved.
  Preserve icons and tooltypes unless changing the defaults is explicitly intended.
- Force a fresh normal release build before packaging; a previous `VERIFY` build can occupy
  the same output filename. Check that VERIFY-only options and instruments are absent.
- Put the new ReadMe entry above the previous author's, and update its requirements line (WHDLoad
  version, memory) to match the slave header.
- Test archive integrity with `"$LHA" t`, then extract the result into a separate temporary
  directory. Require exactly the original member names, every extracted file equal to its
  staged copy, every replaced or added file equal to the current build or source, the member
  list equal to the original's plus the declared additions minus the declared removals, and
  every other file byte-identical to the original. Require the slave and ReadMe to differ from the originals. This verifies package
  contents; it does not replace gameplay checks of the slave.
- Derive the output archive version from the built slave's `$VER` string and require a matching
  ReadMe entry. The release version (`DECL_VERSION`, e.g. `1.2b`) is separate from `ws_Version`,
  which declares the WHDLoad interface version. A "b" suffix marks a beta until play-testing
  is done.

### Intentional installer and icon updates

The replacement procedure above is the default for an unchanged installer. When
installation behavior or defaults intentionally change, declare the additional changed or
added members explicitly and retain byte equality for every other original member. Compare
the extracted archive with that declared member list rather than assuming only two files
may change.

A rewritten installer can start from the WHDLoad developer package's `Install Template`
ReadMe and Install script. Pin the template inputs before adapting them. Retrofit the
original author's supported media and language choices, disk copy filters, decompression,
renaming, manuals, quick references and icon choices. Keep the original credits and release
history; describe only user-visible changes in the new changelog. Match version and date
across the built slaves, ReadMe and package metadata, and check intentional icon defaults
against each variant's actual option semantics.

Stage into a fresh ignored directory. Handle an existing destination drawer and its `.info`
explicitly; do not silently merge or overwrite a played installation and its saves. Quote
paths containing spaces. Static script checks should catch unbalanced expressions, strings
and missing procedure definitions, but do not prove Amiga Installer behavior. Report that
limit if the script has not been executed, and exercise the changed installation branches
before claiming installer acceptance. Keep installable packages distinct from preinstalled
archives: each has its own contents and validation needs.
