# Playbook: improving a game in StingRay's WHDLoad slave repository

For hardware-only failures and cache-coherency checks, also use
[Hardware debugging](new-game-playbook-hardware.md).

> `$PROJECTS` below is the directory that holds the project checkouts (AmigaXDev's parent) and
> `$ARCHIVES` the directory with the game archives the user supplies. Neither is ever written
> into a repo.

> **For an agent working directly in a game branch of the Vesuri fork of StingRay's
> `WHDLoad_Patches` repository** (upstream `MK1Roxxor/WHDLoad_Patches` on GitHub). Start from
> the existing slave source, not an empty repository. Keep the profiling and correctness
> workflow below, but make the fork's `Games/<Game>_WHD.s` (or `Demos/`, `Mags/`) and its
> game-prefixed modules beside it the single authoritative source tree.
>
> Adapted from `new-game-playbook-jotd.md`, itself adapted from `new-game-playbook.md`.
> StingRay's repository is a flat publication of single-file slave sources: no per-game
> directories, build files, ReadMes, installers or icons, and every upstream commit is StingRay's
> own upload. Method references: the JOTD fork's local branch `testdrive2` (commit `ffd6594`;
> `git diff master...testdrive2 -- T/TestDrive2/usr` in `$PROJECTS/jotd_whdload_slaves`) for
> the shape of a focused game change, and the standalone Indianapolis 500 project
> (`$PROJECTS/Indianapolis 500`), whose harness and analysis this fork's work continues. Other
> useful references are Test Drive 2, Battlehawks 1942 (input tape), Their Finest Hour (routine
> models), Legends of Valour (state waits and A/B automation) and Red Baron (a KickEmu slave in
> the JOTD fork). Later projects added: Powerdrome (fast-RAM staged renderer, self-modifying-code
> audit, loader equivalence: §10), Stellar 7 (choosing a tick rate, NTSC timing: §9), Red Baron
> (memory pool, instruction cache, game-speed acceptance, validation budget: §8–§11), Hard
> Drivin' (rendering ceiling, cache audit: §7–§8) and 4D Sports Driving (a clock shared with
> sound, blitter latency: §8–§9).
>
> Current target: branch `indianapolis500`, worktree `$PROJECTS/Indianapolis 500 StingRay`,
> created from `master` at `e05698e`. The main checkout at `$PROJECTS/Stingray_WHDLoad_Patches`
> stays on `master`. Do not recreate the branch, switch the main checkout or initialize a new
> repo. The game's state and open work are in the worktree's `tmp/dev/docs/open-work.md`.
> JOTD's Indianapolis 500 slave (v2.1) is older than StingRay's v3.0 and is not the base: the
> JOTD fork's `indianapolis500` branch and the `$PROJECTS/Indianapolis 500 JOTD` worktree are
> an abandoned, uncommitted first attempt.

The end state ("ready to improve") is defined in §12. Getting there means:
1. a reproducible, cycle-exact trace of real gameplay;
2. a report saying where the frame time goes;
3. a frame-rate figure from a fixed window;
4. a written model of how game time advances.

Patches come after all of that.

---

## 0. Rules (preserve the worktree’s AGENTS.md and existing repository conventions)

- **Never add game, Kickstart or WHDLoad executable bytes**, or generated traces, memory
  dumps, screenshots, input recordings, built slaves or archives to Git. Existing upstream
  installer assets are not a reason to remove or rewrite tracked files. Keep local inputs and
  outputs beneath the worktree’s ignored `tmp/`. Public-domain SDK source/includes are distinct
  from executable bytes; use shared dependencies locally (§10), rather than vendoring an SDK
  into the fork as a side effect. Do not copy another project’s `.gitignore` over this one.
- **Never `pkill fs-uae` or `pkill gdb`.** Other projects run emulators at the same time. Use
  `~/.local/share/amiga/fsuae_common.sh`, which kills only the pid this directory started and
  gives each directory its own gdb-stub port. Kill orphans of your own (a `serve`, a `gdb`, an
  FS-UAE that crashed and left its window up) by pid, after checking the pid is yours.
- Commits: author **and** committer `Vesa Halttunen <vesuri@jormas.com>`; GitHub account
  **Vesuri**; no signing of commits, tags or pushes; `core.hooksPath=/dev/null`; no
  `Co-Authored-By` or assistant-attribution trailers. Nothing work-related in repository
  activity or content. Check `git var GIT_AUTHOR_IDENT`, `git var GIT_COMMITTER_IDENT` and
  effective config before committing; environment variables can override repository config.
  Use one commit per coherent feature and stage explicit game paths. Check `gh`’s selected
  account before GitHub operations: its account selection is shared across projects.
- **This machine's global git config is a work identity** (a work e-mail, a global hooks path,
  signing on). The fork's repository-local config overrides it: `user.name`, `user.email`,
  `user.signingkey` (empty), `commit.gpgsign=false`, `tag.gpgsign=false`, `push.gpgsign=false`,
  `core.hooksPath=/dev/null`. Linked worktrees share it. Upstream has no `AGENTS.md`: the user's
  personal rules are a local, untracked `AGENTS.md` (copied from the JOTD fork) in the main
  checkout and the worktree, with a `CLAUDE.md` that holds only `@AGENTS.md`; both are listed
  with `/tmp/` in the local exclude file.
  Re-check all of this after a fresh clone or a new worktree.
- Addresses in docs are **offsets into the game's code hunk or file**, using the same numbering
  as the slave's patch lists. Never quote absolute addresses, because they move with the memory
  configuration.
- **No performance claim without a measurement**, and only from the right instrument (§7, §8).
- **No local paths in the repo**: no home directories, usernames, `~/Documents/...`, RetroPie or
  amiberry locations, and no paths into other projects. Name another project without its location
  ("AmigaXDev `docs/playbooks/new-game-playbook.md`"). Shared files come from `~/.local/share/amiga`
  through overridable variables in `amiga/env.sh` (§1); scratch output goes to the repo's ignored
  `tmp/`, never a shared `/tmp` location. `~/.local` and `fsuae_common.sh` are the allowed convention.
- **History belongs in git.** Docs describe the current state (how to build, run and measure; how
  the game and the patches work; current numbers; open items). When a finding changes, update the
  reference in place instead of appending a dated section, and delete tools nothing uses.

## 1. Host prerequisites (installed by AmigaXDev)

AmigaXDev's `make setup` installs everything below and `make check` verifies it; its
`docs/environment.md` lists every shared variable. A project's `amiga/env.sh` sources the
shared `~/.local/share/amiga/env.sh` and then sets only what the project changes.

| What | Where | Check |
|---|---|---|
| FS-UAE with the Barto gdb stub (x86_64) | `~/.local/fs-uae/fs-uae` | `fs-uae --version` after `source amiga/env.sh` |
| m68k gdb / objdump / gcc | `~/.local/opt/bin/m68k-amiga-elf-*` | `m68k-amiga-elf-gdb --version` |
| vasm (Motorola syntax) | `~/.local/vasmm68k_mot` | runs and prints usage |
| WHDLoad 20.0 (binary, includes, kickemu sources) | `~/.local/share/amiga/WHDLoad-20.0/` (env `WHDLOAD` = the directory, for `Include/` and `Src/`; `WHDLOAD_BINARY` defaults to `$WHDLOAD/C/WHDLoad`); `WHDLoad/` is 19.2, useful to test older versions | `C/WHDLoad` exists |
| Shared kill/port helper | `~/.local/share/amiga/fsuae_common.sh` | sourced by `run.sh` |
| Host Kickstart 3.1 | `~/.local/share/amiga/Kickstarts/kick40063.A600` (env `KICKSTART`) | |
| Kick images for kickemu slaves | `~/.local/share/amiga/Kickstarts/`: `kick34005.A500` + `.RTB` (env `KICKSTART13`, `RTB`; adapt older donors using `KICK13`), `kick40068.A1200` (env `KICKSTART_A1200`, the 68020 capture machine; its `.RTB` for kick31 slaves isn't there yet) | |
| Workbench 2.04 floppy (gives `C:` and `Libs:`) | `~/.local/share/amiga/Workbenchv2.04rev37.67Workbench.adf` (env `WORKBENCH_ADF`) | |
| LHa for UNIX (creates archives, §13) | `~/.local/share/amiga/lha-compressor/src/lha` (env `LHA`) | runs and prints usage |
| `lha` (extract), `unar`, `lldb` | Homebrew / Xcode | |
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

First establish the ignored harness and working-directory convention in §3, then return here.
Use the same layout for every preinstalled archive:

| Path relative to the harness | Purpose |
|---|---|
| `tmp/archives/<archive>.lha` | retained, unmodified download |
| `tmp/archives/<archive>.lha.sha256` | input archive checksum |
| `tmp/archives/<archive-stem>.files.json` | extracted-file SHA-256 manifest, keyed by relative path |
| `tmp/game/<archive-stem>/` | pristine extraction of the entire archive |
| `tmp/game/<archive-stem>/<installed-drawer>/` | `GAME`: directory containing the slave and its data |
| `tmp/build/` | rebuilt normal and VERIFY slaves, separate from the shipped slave |
| `amiga/.run/dh1/` | disposable writable copy mounted as `DH1:` for this harness |

Keep the archive’s directory structure and spelling. Do not extract into the tracked
`Games/` tree, flatten `data/`, or point `GAME` at `data/` itself. Determine the
installed drawer and slave filename from the archive listing; do not infer them from the
archive basename. An archive may include an outer drawer icon beside the installed drawer:
retain it in the baseline extraction, but mount the installed drawer itself as `DH1:`.
Use a separate archive-stem directory for each version. If a same-named archive has different
bytes, give it a distinct local identifier (for example a checksum suffix); never overwrite
an existing baseline. Inspect a pre-existing extraction instead of extracting over it.

For Indianapolis 500 there are two archives, both StingRay's v3.0 (30.04.2022). The
preinstalled `Indianapolis500_v3.0_0686.lha` (SHA-256
`4841b1dfa2a6dd22b47e23c9f438a67f10a353be44b33fec880af32387a8aba4`) contains the installed
drawer `Indianapolis500/` with `Indianapolis500.Slave`, `Disk.1`, `ReadMe`, `Manual`, `Hints`
and their icons, plus an outer `Indianapolis500.info` (10 files). The installer
`Indianapolis500.lha` (`a0b06b4ca80fc5930a94e0fffc2f6af5e9ca58923be23314794c8176eea10aeb`)
holds the slave, `Install`, the ReadMe, six icon variants and `Source/Indianapolis500_WHD.s`,
byte-identical to the fork's `Games/Indianapolis500_WHD.s` at `e05698e`. Both are retained in
the worktree's `tmp/dev/tmp/archives/` with their checksums and the preinstalled file manifest.
The baseline is `tmp/dev/tmp/game/Indianapolis500_v3.0_0686/Indianapolis500`; the unpacked
installer is `tmp/dev/tmp/installer/Indianapolis500`.

For a **new** archive, use this procedure from the harness root after checking its listing
for unexpected absolute paths, parent-directory components or links. Substitute its names:

```sh
# Example inputs; do not re-run extraction over the prepared Indianapolis 500 baseline.
DOWNLOAD="$ARCHIVES/Indianapolis500_v3.0_0686.lha"
ARCHIVE_NAME=Indianapolis500_v3.0_0686.lha
ARCHIVE_ID=Indianapolis500_v3.0_0686
INSTALLED_DRAWER=Indianapolis500
mkdir -p tmp/archives tmp/game
lsar "$DOWNLOAD"
# Continue after inspecting the listing. Fail if either destination already exists.
(
  set -eu
  test ! -e "tmp/archives/$ARCHIVE_NAME"
  test ! -e "tmp/game/$ARCHIVE_ID"
  cp "$DOWNLOAD" "tmp/archives/$ARCHIVE_NAME"
  (cd tmp/archives && shasum -a 256 "$ARCHIVE_NAME" > "$ARCHIVE_NAME.sha256")
  ARCHIVE="$PWD/tmp/archives/$ARCHIVE_NAME"
  mkdir "tmp/game/$ARCHIVE_ID"
  (cd "tmp/game/$ARCHIVE_ID" && lha xq "$ARCHIVE")
)
```

After extraction, validate the expected slave and game executables, and generate the
`<archive-stem>.files.json` manifest by hashing every regular file in the extraction, including
outer icons. Do not treat a partial extraction as a valid baseline. Keep its manifest outside
the extraction so checks do not hash the manifest itself.

### Run contract: pristine inputs, writable per-launch copy

Set these defaults in the adapted local harness (resolve `HARNESS_ROOT` from the script,
not the caller’s current directory):

```sh
GAME="${GAME:-$HARNESS_ROOT/tmp/game/Indianapolis500_v3.0_0686/Indianapolis500}"
SLAVE_NAME=Indianapolis500.Slave
# No SLAVE override means the shipped slave from GAME: baseline run.
# An explicit SLAVE is the rebuilt normal or VERIFY slave for a development run.
```

Before changing directories, resolve both `GAME` and any `SLAVE` override to absolute paths
and verify they exist. Quote paths throughout. On each launch, stop only this harness’s old
emulator and rebuild its own `amiga/.run/dh0` and `dh1` with the shared process helper. Check
that these disposable paths are inside the harness and distinct from `GAME` before deleting
anything. **Copy** the installed drawer to `dh1`; do not symlink or mount the pristine baseline
writable. Put WHDLoad in the runtime copy and, when `SLAVE` is set, copy that build over
`dh1/$SLAVE_NAME`. Make only the runtime copy writable. Boot with `CD DH1:` and
`WHDLoad Indianapolis500.Slave PRELOAD ...`; the slave reads `Disk.1` from the drawer itself.
A direct slave like this one needs no Kickstart image inside WHDLoad; KickEmu slaves keep theirs
in runtime `DH0:devs/Kickstarts`, using §1 shared inputs.

From the harness root, once the adapted runner and builds exist:

```sh
# Shipped baseline, even if the parent shell exported a SLAVE override:
SLAVE= amiga/run.sh
# Rebuilt development slave, with the same game data:
SLAVE="$PWD/tmp/build/Indianapolis500.Slave" amiga/run.sh
# VERIFY build:
SLAVE="$PWD/tmp/build/Indianapolis500-verify.Slave" amiga/run.sh
```

The Indianapolis 500 harness implements this (`tmp/dev/amiga/run.sh`, from the standalone
project, which took the copy-and-replace pattern from TD2's). It resolves a relative `SLAVE`
against the caller's directory before changing into `amiga/`.

Save games, preferences and mission tapes written during a run belong to disposable `dh1`.
Each launch starts from the same baseline. For a required saved scenario, copy selected files
out before restart and apply them to a **separate**, documented fixture tree or the runtime
copy; never silently promote a previous run’s state into the baseline. Keep fixtures ignored.
For A/B captures, use the same archive hash and fixture manifest, retain the exact selected
slave beside the trace, and check the pristine-file manifest has not changed. Capture one
run at a time per harness; distinct worktrees have distinct runtime directories and ports.

**Check:** the shipped slave and rebuilt slave can each launch against copies of the same
installed drawer; the baseline checksums stay unchanged, and `git status` shows no game data,
archives, runtime files or build products. Preparing the files alone does not pass the boot
check: the runner and unmodified-slave build still need the validation in §4 and §10.

There are two kinds of archive. Work out which one you have:

- **Pre-installed** (Retroplay style: `Game/Game.slave`, `Game/data/...`, `.info` files). This
  is everything you need. TD2: `TestDrive2_v1.5_0588.lha`.
- **Installer** (`GameInstall/Install`, `Game.slave`, often `source/Game*.s`, docs). It has no
  game data; the data comes from original disks. The installer archive is still valuable for
  **the slave's source**. TD2: `TestDrive2.lha`, with JOTD's `source/TestDrive2HD.s`.

The fork already supplies the slave source at `Games/Indianapolis500_WHD.s` (StingRay's other
slaves are `Games/<Game>_WHD.s`, `Demos/...` and `Mags/...`; `_ImagerSlave.s` files are disk
imagers). Inspect that first; the installer archive is useful for a shipped slave and packaging
baseline, not as a second editable source tree. If installed data or original disk images are
missing, identify the required inputs and ask for them. Do not reconstruct a slave whose source
exists. Compare the repository version with the installer's `Source/` and the shipped slave
before attributing behaviour differences to new patches. Keep hashes and archive provenance in
local development notes.

Set `GAME` to the installed drawer under `tmp/game/<archive-stem>/` as above; `run.sh`
mounts a disposable copy on `DH1:`, never the baseline itself.

**Read the slave before booting anything.** From the source, or the header at the start of the
`.slave`, record these in `docs/internals.md` (the doc on how the game and the slave work, §3;
Indianapolis 500: `docs/game.md`):

| Field | Why it matters |
|---|---|
| `ws_BaseMemSize`, `ws_ExpMem` | how much RAM WHDLoad needs, so you can size the machine (§3) |
| kickemu include (`kick13.s`, `kick31.s`) or none | **OS game** (LoadSeg'd executable on an emulated Kickstart) or **direct game** (the slave loads disk images/files into memory and jumps in, no OS). Old slaves (before kickemu) are OS games too: BH's v1.0 calls `resload_LoadKick` and `resload_Patch`es the Kickstart image itself (trackdisk → `Disk.N`, a `LoadSeg` hook), and the game boots from `Disk.1`'s own startup-sequence |
| `ws_config` (JOTD: `slv_config`) / `CUSTOM1..5` / `ws_Flags` | existing options; your patches add theirs here |
| `_patchexe` / `resload_PatchSeg` / `resload_Patch` lists | which file is the game code, which versions are supported (usually by CRC or size), and which instructions are already patched |
| the buffer-swap or copper patch, if any | often the best frame counter (TD2: `PL_P $0588a,set_copper`) |
| the main executable's name and size | the region finder byte-matches it (§6) |

Find the code file. For OS games it is the executable the slave LoadSegs. If the game boots
from disk images, list them (`python3 -m amigaxdev.adf Disk.1`, OFS/FFS) and read `s/startup-sequence`
(BH: `BH`, an Aztec C executable). **If `ws_ExpMem` is just the Kickstart size, the OS has only
BaseMem: the game and all its buffers are in chip RAM** (BH: code at chip `$22F08`), found in the
trace's chip snapshot rather than in the "other" memory dump. TD2: `data/duel`, an
Aztec C overlay executable. Parse its hunk header (`$3F3`, then the hunk sizes) to get each
code/data/BSS hunk's file offset and size. TD2: hunk 0 at file `$28`, `$1156C` bytes; data hunk
`$3A38` file-backed, `$7A70` allocated. For direct games the code is in disk images or raw files
at an address the slave chooses; read it from the slave's `resload_DiskLoad`/`LoadFile` calls.
**The disk image may hold an ordinary hunk executable that the game's own intro loads and
relocates.** I500: the slave loads a 19-track intro to address 0; the intro loads a 7-hunk
executable stored raw at `Disk.1+$1A200` (grep the image for `000003f3`). Parse it like a file
(`i500_report.game_hunks()`). Expect slack: I500's hunk 4 has `$404` bytes before its HUNK_END.
The slave's game patch offsets are then hunk-0 offsets. Confirm the hunk base from a `PL_P`/`PL_PS`
jump into the slave (`4ef9`/`4eb9 <slave address>`) minus its patch-list offset.

**Check:** you can name the code file, its version, its hunk layout, the slave type, and every
existing slave patch with its offset.

## 3. Set up local tooling around the existing game source

Use the existing Indianapolis 500 worktree. Run these inspections there before editing anything:

```sh
cd "$PROJECTS/Indianapolis 500 StingRay"
git status --short --branch
git worktree list
git remote -v
git log --oneline master..HEAD
git var GIT_AUTHOR_IDENT; git var GIT_COMMITTER_IDENT
```

The remote is the personal fork `git@github.com:Vesuri/Stingray_WHDLoad_Patches.git`. No
upstream remote is configured (upstream is `https://github.com/MK1Roxxor/WHDLoad_Patches`).
Inspect any configured upstream before fetching or comparing; do not change remote topology
or publish a branch merely as part of setup. Repo-local identity settings apply to linked
worktrees; verify that no worktree or environment override changes the effective settings.

Keep the upstream layout:

| Location | Purpose |
|---|---|
| `Games/Indianapolis500_WHD.s` | authoritative slave and patch lists |
| `Games/Indianapolis500_<Module>.s` | new patch modules and VERIFY or diagnostic instruments, prefixed with the game's name because the repository is flat (`Motion`, `Spans`, `Colour`, `Line`, `Clear`, `PixelVerify`, `DrivingTest`, `SoftTiming`) |
| `tmp/dev/` | local harness: `amiga/`, `tools/`, `docs/`, build wrapper, inputs and outputs |

The repository has no build file, ReadMe, installer or icon for any game: those live in the
installer archive (§13). StingRay assembles on his Amiga through `SOURCES:` assigns
(`INCDIR SOURCES:INCLUDE/`, `INCLUDE WHDLoad.i`); helper files that his other slaves include by
assign are not in the repository. The Indianapolis 500 modules are included by plain file name
from the main source's directory, so the game's source is complete as committed.

**Preserve upstream bytes.** StingRay's sources are Latin-1 with LF line endings and tabs, and
the Indianapolis 500 banner contains a Latin-1 byte (`$AF`). A tool that rewrites the file as
UTF-8 replaces it with U+FFFD (the standalone copy lost it that way). Edit it byte-wise or with
an editor that keeps Latin-1, and check `git diff` for a changed banner line. `grep` calls the
file binary because of that byte: use `grep -a`.

`/tmp/`, `/AGENTS.md` and `/CLAUDE.md` are in the repository's local exclude file (resolve it
with `git rev-parse --git-path info/exclude`; do not assume `.git` is a directory). Preserve its
existing entries. Check `git check-ignore tmp/dev/probe` before copying anything. This local
exclusion is shared by the repository's worktrees and does not add a tracked `.gitignore` (the
repository has none). Keep local notes local unless their inclusion in the game's source
contribution is deliberate. Inspect staged paths before every commit.

The Indianapolis 500 harness was copied from the standalone project, which already had a full,
working one (it had been adapted from TD2's), rather than from TD2 again:

```sh
# Done for Indianapolis 500. For another game, from its worktree root:
export FORK_ROOT="$PWD"
export GAME_SOURCE="$FORK_ROOT/Games"
mkdir -p tmp/dev/amiga tmp/dev/tools tmp/dev/docs tmp/dev/tmp/build
cd tmp/dev
DONOR="$PROJECTS/Indianapolis 500"     # or Test Drive 2, per the table below
cp "$DONOR/amiga/env.sh" "$DONOR/amiga/run.sh" amiga/
# Select only needed tools and their imports from the donor or the other reference projects.
# Adapt root detection, game names, source paths and output paths before running them.
```

For Indianapolis 500 only the game and source paths needed changing: the `GAME` default in
`amiga/run.sh`, `fixed_window.sh` and `i500_report.py`, the source path in `check_disabled.py`
(`Games/Indianapolis500_WHD.s`, three levels above `tmp/dev/tools`), and a new
`tools/build.sh`. The standalone project's `whdload/` copy is no longer edited.

**Command convention for the remaining sections:** `amiga/`, `tools/`, `docs/`, `tmp/` and
`dist/` are relative to the harness root (`$FORK_ROOT/tmp/dev`), not the Git root. Thus all
captures and local docs stay below the worktree's ignored `tmp/`. Any `whdload/` reference
in a donor tool or example means its old source location: adapt it to `$GAME_SOURCE` and
explicit build outputs under the harness `tmp/build/`; do not create a copied slave tree.
Set these roots in the local environment/build wrapper so they survive a new shell, and quote
all paths (the worktree name contains spaces). Ensure the harness keeps its own process,
port and log directory; do not accidentally resolve it to the main Git checkout.

Copy the tools you need and discard unused ones after setup. Don't copy `barto.py`, `disd.py`,
`hotspots.py`, `dis.sh`, `adf.py`, `patchlist.py` or `local_env.py` from an older repo: take
`bh.py` (the shared gdb server; rename it) and `_amigaxdev.py` (the shim that puts `$AMIGA_PYLIB`
on `sys.path`) from Battlehawks 1942, import `amigaxdev.barto` and `amigaxdev.env`, and run
`python3 -m amigaxdev.disasm|adf|patchlist` after `. amiga/env.sh` (AmigaXDev
`docs/environment.md`, "Shared tools"). Copy generic `compare_state.py` from Their Finest Hour if suitable, and
validate it on this game. Remove inherited machine paths and game assumptions. Shared inputs
must use §1 variables. Changes intended for the fork must contain no host-specific paths,
including in source comments (the port dropped comments naming local docs and tools).

What is generic and what has to be adapted:

| File | Generic | Adapt |
|---|---|---|
| `amigaxdev.barto` (shared, imported) | trace parser, all of it | nothing |
| `bh.py` (rename it, here `game.py`) | `Server(name, root=ROOT).main(argv)` from `amigaxdev.gdbserve`: `serve/stop/cont/shot/wait/until/gdb/profile/quit`, lldb window fix, `BOOT_BREAK` | the name; game commands go in `commands={'op': fn(server, g, rest)}` (they can replace a built-in); `profile_window=False` where the stub needs no window fix. Shared-code changes (`BASETEXT_VM` for a new FS-UAE binary) go to AmigaXDev |
| `amiga/run.sh` | host boot, DH0/DH1, startup-sequence, port claim | `GAME`, slave file name, kick images copied to `DH0:devs/Kickstarts` (kick13 needs `kick34005.A500`+`.RTB`; kick31 needs `kick40068.A1200`+`.RTB`; direct slaves need none) |
| `td2_report.py` `regions()` | byte-match voting, BPTR chain to the data hunk | code file path and hunk offset/size, kick image (or none), slave path; `Namer` function starts (`link a5` is Aztec C; SAS/C and asm differ, see §8). I500's version parses the hunk file from the disk image, votes each file-backed hunk into the dump *or* the trace's chip snapshot, and finds the live slave (below) |
| `frames.py`, `swap_fields.py` | DMA slot counting, blitter-poll counting | frame marker (§7), interrupt-handler addresses (Kick 1.3 level-3 `$FC0D14`/BLIT `$FC0D38`/VERTB `$FC0D4A` only apply to a kick13 game; a direct game has its own handlers, read the level-3 vector at `$6C`) |
| `profile_demo.sh`, `ingame.py` | boot, poll, trace, dump | the "in gameplay" pixel test (TD2: sky blue above the dashboard) |
| `fixed_window.sh` | calibrate-then-reboot, retained slave, `STATE_ONLY`/`SWAP_ONLY`/`SERVE_WAIT` | anchor offset and the state watched at the anchor (§6) |
| `state_fields.py`, `state_writers.py` | per-field snapshots at the VBL entry; finding `d16(a4)` stores | what to snapshot: TD2 and TFH dump the data hunk; I500 keeps its variables at absolute addresses inside the code hunk, so it dumps hunk 0. `state_writers.py` only finds `d16(a4)` stores (Aztec C), so an asm game needs an `abs.l` variant. `task_state.py` and `state_watch.py` are TD2-specific: don't copy them |
| `compare_state.py` (TFH's) | compares the whole data hunk; a longword pointing into the code or data hunk at the same offset in both runs counts as equal, so builds that load the game elsewhere still compare | hunk sizes, `a4` bias. **TD2's version compares TD2's variable table and reports "identical" on any other game**: TFH quoted meaningless "identical state" results from it for a day. Before trusting any compare, check that two runs of the same build compare equal and two different scenes do not |

Keep a read-first index in the local harness notes, with these current-state documents. For
Indianapolis 500 (in `tmp/dev/docs/`, carried over from the standalone project):

| Doc (relative to the harness) | Holds |
|---|---|
| `docs/open-work.md` | current status, uncertainties and ordered next items |
| `docs/profiling.md` | source root, build, inputs, variables, run/capture/check commands (the playbook's `development.md`) |
| `docs/game.md`, `docs/slave.md` | the game's memory, time model and renderer; the slave's options, features, hooks, verification and measurements (the playbook's `internals.md`) |
| `docs/simulation-feasibility.md` | the analysis of a faster simulation |

The local, excluded `AGENTS.md` at the worktree root carries the rules, the doc index and the
current state for the next agent session, after the personal commit rules; a local `CLAUDE.md`
holding only `@AGENTS.md` lets Claude Code read it.

Do not commit a standalone-project scaffold at the fork's root. Keep the eventual game change
as focused as `testdrive2`: the game's source files only. Upstream-facing explanation belongs in
the source's history block and comments (§13).

### Indianapolis 500 facts (from the source; details in `tmp/dev/docs/game.md`)

StingRay's v3.0 (30.04.2022) declares `ws_Version` 17 (for `ws_config`),
`WHDLF_NoError|WHDLF_ClearMem|WHDLF_EmulTrap`, BaseMem `$80000`, ExpMem 512 KB, quit key Del.
It is a direct game: it loads 19×`$1600` bytes of `Disk.1` to 0, accepts only the SPS 686
version (CRC16 `$B46E`), patches the intro and jumps to `intro:$a040`. The intro loads a 7-hunk
executable stored raw at `Disk.1+$1A200`; the slave's `PL_GAME` offsets are hunk-0 offsets
(`game:`). Saves go to separate files. `Enable_Cache` marks BaseMem non-cacheable, so without
the MMU WHDLoad turns every cache off: measure with WHDLoad's `DCACHE`. Preserve the protection
removal, the 68000 quit key, the 040/060 level-2 acknowledge fixes and the save handling.

## 4. First boot (windowed, real speed)

Boot the preserved shipped slave first. Also perform the unmodified-source build and baseline
comparison in §10 before adding any instrumentation or game changes. Pass the selected slave
explicitly with `SLAVE`; adapt donor defaults so they cannot silently run an old TD2 build.

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
  plus a user-supplied `CUSTOM5` stops the boot at an AmigaDOS argument error (Stellar 7).

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

Facts about this stub, all verified the hard way:

- **Attach within 20 s of launch.** `--remote_debugger=20` with no trigger stops servicing the
  port after 20 s. `serve` connects as soon as the port listens and continues from reset.
- **The stub is read-only.** `M`/`P`/`G` packets are silently ignored, so `set var` does
  nothing. Every change to the game must go through the slave.
- **Emulated time stops while gdb holds the CPU**, so stops and the lldb attach cost no emulated
  time.
- **Without a trigger the profiler records no PCs.** The window `[baseText, +sizeText)` reads as
  `[0x0100007f, +0)`. The shared server's `profile` fixes it each time by lldb-writing `0`/`0x7fffffff` at
  link-time `0x32dea04` plus the slide. For a different FS-UAE binary, re-derive that address
  from the `GDBSERVER: enabled` setup and `start_cpu_profiler` (TD2 `docs/profiling.md` §3). The
  assert fails loudly if it's wrong.
- **Screenshots come only from traces** (`shot`). macOS denies screen capture to this process,
  and posted key events never reach FS-UAE. A shot taken at an arbitrary checkpoint (a keyboard
  task, a tape step) can catch a partial redraw: stop at the frame-publication instruction (§7)
  before saving a picture you will compare (4D Sports Driving).
- `gdb` splits arguments at spaces, and repo paths often contain them (`Their Finest Hour`). gdb's
  working directory must be the harness root, so dump to a **harness-relative** path (`tmp/x-code.bin`), then move
  the file. Python 3.12's `tempfile.mkdtemp(dir='tmp')` returns an absolute path: pass it through
  `os.path.relpath` before handing it to gdb. Don't use `/tmp`: parallel jobs share it.
- At most **100 fields** per `monitor profile`, about 5.4 MB per field.
- **One capture at a time per repo.** `fsuae_common.sh` gives each directory its own port, so
  two captures from the same repo collide on the debugger socket. Run them in sequence.
- `run.sh` changes into `amiga/` before copying the slave, so resolve a relative `SLAVE` against
  the caller's directory first (I500 `run.sh`).
- The **68030 backend emits no instruction trace**. Count frames there with `SWAP_ONLY` (§7).
  The cycle-exact 68030/68040/68060 configurations have no validated instruction timing, and with
  `blitter_cycle_exact=false` their traces carry no blitter DMA records although the blitter runs.
  Report those routine and blitter costs as unavailable, never as zero, and never transfer A500
  percentages to them (Hard Drivin').
- **lldb can be slow to attach.** I500 (same FS-UAE binary, 2026-10-05): ~40 s per attach, so
  TD2's two attaches per capture (image list, then write) overran the 60 s timeout. Use one attach
  that computes the slide and writes the window in lldb's Python (`LLDB_FIX` in `i500.py`), with a
  longer timeout.
- **`until` blocks the server** until its breakpoint hits. If the address is never reached, the
  only way out is killing your own emulator by `amiga/.run/fsuae.pid`. Hardware watchpoints
  (`watch`) did not fire within minutes on I500. Prefer counted breakpoints: `break *A`,
  `ignore $bpnum N`, `continue` (the breakpoint number grows each time, so use `$bpnum`). About
  3 s per 100 fields in warp.
- The recorded **SR is stale** (UAE updates it lazily), so tell supervisor and user code apart by
  which stack SP is in.
- **Native arm64 FS-UAE** (`~/.local/share/amiga/fs-uae-arm/fs-uae`, env `FSUAE`): host lldb
  cannot attach, so the profiler window can't be written from outside. LoV's VERIFY-only
  `PROFILER_WINDOW` fixture (`PROFILE_WINDOW=guest`) configures it from the guest at the tape
  anchor: in VBL context it saves SR, the current process's segment-list/task-number fields and
  some chip scratch, presents a synthetic segment, waits for the harness's `qOffsets`
  acknowledgement, then restores everything before tracing (`profile_window_check.py` verifies
  the restore). Barto then stores RAM PCs relative to the profiler start (ROM PCs and IRQ markers
  stay absolute): keep the acknowledged base in a `trace.pc-base` sidecar and `amigaxdev.barto`
  normalizes it. `until` should wait in the background with a timeout (`UNTIL_TIMEOUT`) and stop
  the capture cleanly, so a stalled route can still be dumped and quit.

**Check:** `barto.load()` on the trace shows instruction records **with PCs**, and the
screenshot shows the moment you expected.

## 6. Map memory, then find a reproducible gameplay window

**Regions.** Dump the "other" memory, where WHDLoad puts the slave's memory: `$C00000` slow RAM
with no fast RAM, `$200000` with fast RAM, and chip from address 0 on a machine with neither
(a stock A1200: TFH). Use `game.py gdb 'dump binary memory tmp/x.bin BASE END'`.
Adapt `regions()` until `td2_report.py` names the code hunk, the data hunk, the kick image and
the slave. Relocations make an exact compare impossible, so 16-byte windows vote for a base.
Also, **the PRELOAD copy of the file is in memory too**: follow LoadSeg's BPTR chain from the
code hunk to the data hunk rather than byte-searching for it. For a direct game, look for the
code in base memory (chip, included in the trace's chip snapshot) *and* in the expansion memory.
I500 runs from ExpMem in slow RAM (for example `$CFFC0C` on the A500-eq. and `$57AC0C` with fast
RAM; the addresses move with the slave's size and the memory configuration).

**Which slave copy is live.** Several slave-shaped copies sit in memory (PRELOAD, file). The live
one has its `resload` pointer filled in and some header bytes rewritten by WHDLoad, so match the
code after the pointer and require it to be non-zero. Trim the file to the hunk length first:
the trailing `HUNK_END` is not in memory. Anything the tools read *inside* the slave (a tape
counter, a marker) must be searched for from the live copy's start: with 8 MB of fast RAM
BH's marker appeared three times and the first one was WHDLoad's file copy, frozen at 0.
And a byte-vote locator needs a quorum (a third of the windows, address ≥ dump base): DOS
buffers in chip RAM held pieces of `BH` and outvoted nothing, giving a negative "base".

**Driving.** Prefer the attract demo when there is one (TD2's and I500's drive themselves). Otherwise:
- **Not** FS-UAE input recordings: in this FS-UAE build playback never works. FS-UAE emits two
  events of its own at startup (2263, 2272, whatever the ports are), and recording an event
  during playback truncates the recording at the play position, i.e. at 0. (Recording works;
  `KEY_RETURN` = 164 in this binary; Battlehawks `tools/splice_rec.py` splices events.)
- For an OS game, a **VERIFY input tape in the slave** (Battlehawks `whdload/tape.s`, game
  independent): `_cb_dosLoadSeg` starts an Exec task whose TCB, stack and I/O live in the slave,
  counts fields with `WaitTOF` and types raw keys with `input.device` `IND_WRITEEVENT`. It
  publishes a marker and its field count so `fixed_window.sh` can poll it. Map the screens first
  (a `shot` at each tape step): BH needed four Returns after the credits (menu, mission, ready
  room, and the manual check, which the slave "removes" but still waits for Return). The timing
  changes with the slave (v1.0 vs KickEmu), so retime the tape when the boot changes.
  **Find out how the game consumes a key** before scripting gameplay: BH takes one IDCMP
  character per frame, and its controller turns one cursor character into full stick for one
  frame. So the bank grows with the *number* of presses, not with how long a key is held (a
  real keyboard's auto-repeat sends many). Hold each press longer than a frame, and wait until
  the gameplay loop is running (BH's first presses 100 fields after the last menu key were lost).
- **Feed gameplay input inside the game's frame loop**, on frame numbers, once the game
  steps per frame: BH's VERIFY slave hooks the loop's call of its key reader and returns a
  scripted character on listed frames. Then every CPU and every run gets the same input on
  the same frames, the window (a frame number) shows the same scene everywhere, and game state
  can be compared across CPUs. Two weaker versions failed: keys typed at fixed fields put the
  68020's frame 90 before the bank (a different scene), and a task polling the frame counter
  once per field let presses slip a frame when debugger stops shifted the phase.
- For a gameplay window, script **some manoeuvring**. BH's first flight is straight and level
  over flat-shaded sea: 1 % of the view changes per frame, which flatters the delta c2p and
  under-loads the renderer. The user asked for a left circle (8 presses) as the benchmark.
- **Wait on game state, not on fields** (LoV `whdload/tape.s`, a mouse game): screens arrive
  hundreds of fields apart from route to route, so fixed waits either misfire or waste minutes.
  LoV's tape writes the pointer into the window's `MouseX/MouseY` and the buttons into the game's
  debounced state from its VBL server, and also hooks the game's button hit test to remember the
  list it was given: a `W` entry holds until that list has a given button id under the pointer,
  an `H` entry until the heading reaches a value, an `A` entry marks the anchor. Panels that poll
  through other code are invisible to such a wait (LoV's conversation panel): click them away
  blindly at intervals, and reject a window that starts inside one.
- For a direct game, hook the game's joystick read and feed it from a table indexed by
  field. This is what TD2's `CUSTOM5` fixtures do. Neither tape needs debugger writes.

**Reproducibility. This is the most important step; everything after depends on it.**
1. Find the game's sources of entropy: reads of `VHPOSR`/`VPOSR` (`$dff004/6`), CIA timers,
   `DateStamp`, uninitialised memory, **and input ports**. TD2's RNG mixed in VHPOSR, so the demo
   differed on every boot. Remove them in a **VERIFY build only**, gated by an option (TD2:
   `CUSTOM3`). I500 reads the port-0 mouse counters (JOY0DAT) every frame, and their raw value
   differed between boots. The host mouse feeds port 0 even with input grab off, so a mouse moving
   over the window injects input. Capture with nothing in port 0: **`joystick_port_0=none` is not
   enough in FS-UAE**: it unplugs the host device but the port's *mode* stays `mouse` (the
   default for port 0) and the host mouse still moves its counters. Also pass
   `--joystick_port_0_mode=nothing` (Battlehawks `run.sh` does both for `JOY0=none`). With that,
   BH's two captures became identical in every register and DMA record. And people watching
   the emulator window can touch it: tell them, or treat a touched run as void.
2. Boot with `DETERMINISTIC=1`.
3. **Anchor on game state, not on wall time or screenshots.** Find a store that marks the start
   of play. TD2: the race-clock reset `move.l #1,-10146(a4)` at `duel:0bbf8`, then the gameplay
   loop at `duel:05a4c`. Arm it at CPU reset: `fixed_window.sh` boots once to learn the load
   address, caches it, and reboots with `BOOT_BREAK` armed so a warp boot can't run past it.
   Confirm with a gdb watchpoint. A simpler anchor that worked on I500: **the first execution
   since boot of the renderer's end-of-frame**, if menus and credits don't use that renderer.
   I500's `game:0b57e` (the swap request) is first hit at the end of the demo's first frame.
   `SKIP_FRAMES=N` then gives later windows. **A breakpoint armed from reset makes warp slow**:
   BH's flight starts ~4600 fields after boot and `BOOT_BREAK` did not get there in 5 minutes.
   With a tape, boot with no breakpoint, poll the tape's field counter (read-only; emulated time
   stops while gdb holds the CPU) and arm the anchor a few hundred fields before the last key. To find the start, step from the game's entry with
   counted VBL breakpoints and a `shot` every 100 fields. Traces of the transition show which code
   runs first.
4. Retain the exact slave with every capture (`OUT/slave.slave`), and analyse with
   `SLAVE=$OUT/slave.slave`. A different slave size moves the region bounds and can hide the
   frame marker.

**Check:** two fresh boots of the fixed window give byte-identical first- and last-field
screenshots and identical state snapshots. Stronger, and cheap: compare every field's instruction
records, DMA records and screenshot with `barto` (I500: all identical with `JOY0=none`;
Battlehawks `tools/compare_traces.py`). BH: identical after the port-mode fix above (before it, JOY0DAT read `$0000`
in one boot and `$0101` in the other). Don't
`cmp` whole trace files: the slow-RAM snapshot holds WHDLoad/host bytes that differ between boots. Never compare two windows taken at arbitrary demo
moments: TD2's demo varied between 4.3 and 7.2 fps by scenery alone.

**Anchor on the game's frame counter, and hold the emulator while searching memory.** With
8 MB to dump and search, warp left running got thousands of fields past the arming point; and
a 0.2 s poll step in warp overshoots hundreds of fields. BH's window opens at the c2p pass of
flight frame N by the game's own counter, which is deterministic whatever the poll did.

**Never edit a script while a capture is running it.** bash reads scripts as it executes, so an
edit to `fixed_window.sh` mid-run makes it execute garbage from a shifted offset (BH: `h: command
not found` after 10 minutes). Copy the script, or edit only between runs.

**Memory, PRELOAD and blinking.** A disk-image slave without PRELOAD does a WHDLoad OS switch
for every disk read: the screen blinks through the boot and loads take longer, enough to break a
field-timed tape. BH's slave got 512 KB of fast memory (only DMA data in chip RAM), which no longer left room in
1.5 MB of slow RAM to preload three 880 KB images. The capture machine is now 68000 + 512 KB chip
+ 8 MB Zorro II fast (the user's call). KickEmu's `IOCACHE` only caches `HDINIT` files, not
disk images.

## 7. A frame counter you can trust

Find the instruction that makes a new frame visible:
- a COP1LC write (TD2: the slave's `set_copper`, `move.l a0,$dff080`; I500: the game's own VBL
  handler, `game:0b2e2`, executed only when the renderer has set a swap-request bit);
- `BPLxPT` writes in a copper list;
- `LoadView`/`ScrollVPort`;
- a double-buffer flag flip;
- or, with **one displayed buffer**, the pass that writes it. BH renders chunky and converts with a
  delta c2p (`bh:1a2c2`) straight into the visible bitplanes; the c2p entry is the frame counter.
  Check the destination planes across frames before assuming double buffering.

A VBL handler that rewrites the bitplane pointers every field is not a frame counter by itself:
Hard Drivin's handler writes `BPLxPT` on every VBL and publishes a new frame only through a
conditional buffer exchange, which is the marker. Where the trace is empty (68030 and up), a
read-only watch of the front-buffer pointer at successive VBLs counts the exchanges; check first
that it reproduces the swap breakpoints on the 68000 and 68020. Where you can, confirm the
marker against the display: the COP1LC or pointer write must be followed by bitplane DMA from the
new buffer in the next field (4D Sports Driving).

The level-3 vector may not be the Kickstart's: BH installs its own sound handler there and chains
to the ROM handler past its prologue. Count level-3 entries at whatever `$6C` holds.

Count those per PAL field. Over 100 fields that gives `fields/frame` and fps. Write it into
`frames.py`, and as read-only breakpoints into `swap_fields.py` for CPUs whose trace is empty.

Also find how the swap is timed: a beam wait, `WaitTOF`, or a VBL handshake. Count the CPU's
swap-wait spin separately from blitter waits (I500: `game:0b5ae`, 2.5% of an A500 frame and 10.5%
on a 68020). And find every blitter-wait idiom, not just `btst #6,2(a6)`: I500 has 78 absolute
`btst #6,$dff002` and a register form `btst d4,(a6)` with `a6=$dff002`, the hottest of them. TD2's slave waits
for VPOS ≥ `$84`, so frames are quantised to whole fields and the ceiling is 25 fps. That wait
is JOTD's flicker fix: **don't touch** it without testing a fast CPU for tearing.

**Check:** `SWAP_ONLY` and the full trace give the identical swap pattern on the same window.

## 8. Baseline profile

Run on the A500-equivalent machine, in the fixed window:

```sh
tools/fixed_window.sh tmp/prof/base
python3 tools/td2_report.py tmp/prof/base/trace.bin tmp/prof/base/code.bin --base 0xc00000
python3 tools/frames.py     tmp/prof/base/trace.bin tmp/prof/base/code.bin 0xc00000
python3 -m amigaxdev.disasm hotspots --label game tmp/prof/base/trace.bin tmp/prof/base/code.bin 0xc00000 <hunk> <off,...>
python3 -m amigaxdev.disasm disd tmp/prof/base/code.bin 0xc00000 <hunk> <start> <end>
```

Record, in `docs/internals.md` (current measurements) with the command in `docs/development.md`
(Indianapolis 500: `docs/slave.md` and `docs/profiling.md`):
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
- **Contexts** come from SP ranges. TD2 had a main task, a second game task, OS device tasks and
  the supervisor stack. A direct game may run everything, interrupts included, on one supervisor
  stack. Then interrupt work shows up as "calls" from whatever it interrupted (I500: the SOFT
  handler's `game:27b78` "under" `0a908`/`0bb42`). Identify handlers from the vectors at
  `$64..$78` in the chip snapshot and count their entries instead.
- **Asm with absolute addressing** (I500): take function starts from every static `jsr abs.l` and
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

**The machine matrix.** The projects converged on one set, all running the same build and window:
the A500-equivalent (68000, 512 KB chip + 1.5 MB slow); a stock A1200 (68EC020, 2 MB chip, no
fast RAM), which TFH found behaves differently from an A1200 with fast RAM; an A1200 with 4–8 MB
fast; a cycle-exact 68030/50 with and without WHDLoad's `MMU` option, whose out-of-box cache states
differ (Red Baron); and a 68040/25 and 68060/50 as `-NOMMU` (below). Add NTSC cells only when the
game supports NTSC (§9). Script the matrix to run one capture at a time (Stellar 7
`rate_matrix.sh`, LoV `ab_window.sh`) and give each boot a deadline, so a hung cell fails instead
of blocking the queue.

**Find the ceiling before choosing work** (Hard Drivin'). On the fastest configuration, build a
matched control and a bypass with identical size, placement and alignment that differ only in two
bytes (`rts` at the polygon filler's entry), and also run the control with an instant blitter.
Hard Drivin's control drew 38.5 fps, instant blits 44.2 and no polygons 49.9: no publication cap,
and a material blitter and bus share. Use the matched control as the reference, not the regular
build, whose different layout changes the timing. The two gains don't add, and the bypass is not
a visual test. Read the DMA slot shares beside the blitter-wait cycles: 4D Sports Driving's 68020
spent 30% of its frame in blitter waits with half the chip-bus slots free, so the cost was the
latency of many small serial blits, not bandwidth.

**68040/68060 in FS-UAE.** Use `CPU=68040-NOMMU` (likewise for the 060) with the cycle-exact
68030 options and the frequency changed. With plain `68040` FS-UAE emulates the MMU, WHDLoad
turns it on, and the MMU loop then ignores the frequency and the chip timing. The generic loop
(`cycle_exact=false`, `cpu_compatible=false`) ignores them as well. Sanity check: an 8 MHz run
must be slower than a 25 MHz one (I500's first 68040 runs gave identical fps at 8, 25 and 40 MHz).
`cpu_speed=max` is not a real machine: chip accesses are nearly free there, and so is an
instant blitter, so neither is a ceiling for real hardware.
Run a separate functional boot with the MMU on (`CPU=68040`, `68060`). FS-UAE's MMU core has no
real cache model, so that boot tests MMU setup and game logic, not cache coherency, and its timing
is not comparable (Powerdrome, Hard Drivin'). Real-hardware cache failures are in
[Hardware debugging](new-game-playbook-hardware.md).

**Caches on fast CPUs.** Without an MMU (a 68020, or a 68030 without WHDLoad's `MMU` option)
WHDLoad keeps the caches off, and many old slaves switch them off themselves. Know which state a
68020/68030 figure was taken in before comparing it (TFH's slave now defines KickEmu's `CACHE`).
A slave that marks BaseMem non-cacheable (`WCPUF_Base_NC`, as StingRay's I500 slave does)
makes WHDLoad turn **every** cache off without the MMU: all of I500's early 68020/68030 numbers
were uncached. Measure with WHDLoad's `DCACHE` (or `CACHE`) when the slave leaves caches alone.
Whether the slave manages caches is a per-game decision for the user: I500 leaves them to
WHDLoad's options (and its ReadMe recommends `DCache`), TFH enables KickEmu's `CACHE`.

Record the cache state behind every figure from the hardware, not from the API. A VERIFY-only
boot can log `CACR` right after the slave's `resload_SetCPU` (Hard Drivin'); the API state
reports instruction and data caches requested even on CPUs that have neither. Read `CACR` only
on a 68020 or later (the 68000 has none, so never execute `MOVEC` there), and keep the audit out
of the normal build: `resload_Log` needs WHDLoad 18. When KickEmu's non-cacheable BaseMem has
turned every cache off without the MMU, enabling only the instruction cache through
`resload_SetCPU`, leaving the data cache as WHDLoad set it and respecting `NoCache`, gained 10% on
a 68020 and 7% on a 68030 without the `MMU` option (Red Baron). Like any cache policy in the
slave, that is the user's decision: I500's user rejected a slave that enables caches itself.

For hardware-only black screens, stale executable stubs and WHDLoad dump analysis, see
[Hardware debugging](new-game-playbook-hardware.md).

## 9. Understand game time before optimising anything

For a fixed-step replacement, also read [fixed-time simulation](fixed-time-simulation.md):
completed-tick versus elapsed-field checks, historical input, native pauses and control feel.

This is where TD2 spent most of its effort, and it was the right call. A faster renderer is
worthless if it also speeds the game up, and pointless if the simulation only moves things
8 times a second. Answer these with measurements:

1. **Time sources.** Which does the game read? VBL counters, CIA timers, `timer.device`,
   frame-count deltas, or nothing (a fixed step per rendered frame)? Grep the binary for
   `$dff004/6`, `$bfe801/$bfd800`, `$6C` vector installs and OS calls, and confirm with traces.
   Also grep **every** CIA timer register (`$bfe401..$bfe701`, `$bfd400..$bfd700`, CRA/CRB, ICR),
   in the loader/intro too: I500's hunk 0 never programs its clock. The intro sets CIA-A timer B
   to 59.7 Hz, and the game divides it by 4 into a SOFT (level-1) interrupt.
   A tick-driven main loop **caps the frame rate at the tick rate**. I500: 15.2 fps on a 25 MHz
   68030 against a 14.9 Hz tick. Run the fast-CPU `SWAP_ONLY` early, because it shows the ceiling.
   **Check the clock's rate against emulated time.** A timer that the sound code also programs
   can run the game at the wrong speed: 4D Sports Driving's sound driver reloads the shared CIA-B
   latch, so its 10 Hz simulation makes 8.3 steps/s on the A500 and game time runs 17% slow.
   Measure steps per second and game clock against emulated time on every machine first.
2. **The state map.** Find the variables that *are* the game: position, speed, clock, opponent
   state, RNG, lives, and so on. Locate them by watchpoints on what changes on screen, then
   `state_writers.py`. Snapshot the data hunk every field at the VBL entry (`STATE_FIELDS=N`) and
   compare with TFH's `compare_state.py` (§3).
3. **The coupling test.** Run the same fixed window on a 68000, a 68020 with fast RAM, and with
   deliberately slowed drawing (a VERIFY-only delay in the draw path; TD2: `CUSTOM4`). Compare
   state field-by-field with `compare_state.py`. Identical state at different fps means the
   simulation is already decoupled. Divergence tells you exactly where it is coupled.
   In a coupled game a field-indexed input tape feeds different inputs per simulation step once
   drawing slows, so the slowed run legitimately reaches a different scene (Hard Drivin's slowed
   tape crashed at field 594 instead of jumping): compare per step, with the input each step
   consumed, not the same scene at the same field. Keep the slow-drawing instrument from
   disturbing what it measures: count VBL transitions in the handler and wait N of them before
   the frame is marked ready, with no `STOP`, host sleep or state writes; preserve the flags the
   displaced instruction sets; and install nothing when the option is 0 (Hard Drivin'
   `VERIFY_SLOW`).
4. **Tasks and interrupts.** Which context advances the simulation? TD2 had a separate 8.33 Hz
   simulation task, plus drawing that shared the RNG. Use `task_state.py` and SP ranges.
5. **Boot benchmarks.** The time step may come from a benchmark at boot rather than a clock. TFH
   draws a test scene, sets `T = 380 / fields taken`, and advances `1/T` s of game time per frame,
   so game speed is right only at the frame rate the benchmark predicted (the A500 ran 1.9× real
   time, a 68030/50 at 0.55×). Check what else reads that value (TFH: ground detail, menus) before
   changing it: a per-frame T can replace it in the flight loop while the boot value stays.
   Smooth a per-frame T. TFH first set T from the last frame alone; with uneven frame lengths T
   alternated (25 and 17 on the 68020), so intervals the game counts in multiples of T (a gun's
   reload T/3, a bullet's life 2T) jittered between 12 and 20 fields. T from the average frame
   length, with the time owed carried, gave 14–18 fields at unchanged game speed. Large T also
   exposes truncation: carrying 16.16 fractions in step lengths and turn rates took TFH's 68030/50
   ground speed from 4,649 to the nominal 4,712 units/s.
6. **PAL and NTSC.** Find out whether anything assumes 50 fields per second. To detect the rate,
   take the beam's highest line over a field (PAL 312, NTSC 262; threshold 288), reading
   `VPOSR`/`VHPOSR` twice so a read across line 255/256 isn't taken as a wrap (TFH `timing.s`).
   NTSC runs need FS-UAE's core option `uae_ntsc=true`: the frontend's `ntsc_mode=1` alone left
   this build in PAL timing, so its "60 Hz" results were PAL (Stellar 7). The shared launcher's
   `NTSC=1` passes both. GLib queue warnings appear in successful PAL and NTSC runs alike and are
   not a stall. Have the capture driver compare the mode it asked for with the measured field
   rate (the beam's highest line, or Exec's) and fail on a mismatch.

**Raising a tick-capped frame rate** (I500): remove the main loop's tick wait, snapshot the
published state (camera, car poses) at the simulation tick's common exit, and rewrite only the
renderer's copies each frame with α = time since that exit / tick period. Interpolation
(`prev + (cur − prev) × α`) is smooth but shows the scene one tick late; extrapolation
(`cur + (cur − prev) × α`) removes that delay but overshoots at sudden changes. Snap at cuts and
teleports, wrap track coordinates and take angles by the shortest arc. Input sampling and the
simulation stay at the tick rate. **Validate on real gameplay, not only the demo:** I500's
cockpit prepares its camera on a different path (`game:160..172`) from the demo cameras, and
demo-only checks missed that interpolation never ran while driving. Add a test build that
drives the native menus with a held input (I500 `DRIVING_TEST`) and check frames within one
tick actually move.

**Choosing a simulation rate.** Price the tick on the A500 first: a finer fixed tick multiplies
the simulation cost, and on a 68000 it can leave nothing for drawing. Stellar 7's native update
cost about 90k cycles of the 97k available per NTSC field, so 60 Hz substeps presented 0.4 fps;
two dozen accepted optimisations took the tick from 137k to 90k cycles against a 40k target, a
structural gap no tuning closes. Red Baron's 225-unit world quantum needed 101% of an A500 in a
squadron scene, and LoV's 25 Hz tick dropped the A500 from 3.3 to 1.2 fps. What worked: keep the
native step on the 68000 (Stellar 7's 5 Hz, Red Baron's original 450-unit clamp) and use a finer
step only where it measures affordable (TD2's per-CPU tick period, Red Baron's 225 units on
68020+), chosen once at start and never changed mid-game. Decide with a measured matrix, not a
cost model: Stellar 7's model predicted 3–4 fps at 15–20 Hz, but only the native 5 Hz met both
A500 gates. If the steps per native update become a build constant (Stellar 7 `S60_SUBSTEPS`),
the native-rate build must stay byte-identical, every constant derived from the step count must
be found (grep the patch sources, fixtures and checkers for the old literals), and states at
native boundaries are compared across step counts with every divergence classified. Interpolate
only where frames are shorter than a tick: on the 68000 Red Baron presents the latest state and
skips pose capture (23k cycles per tick) and blending (170k per frame).

**Acceptance for game speed** (Red Baron, adopted once whole-state identity across CPUs proved
unreachable and unnecessary): at equal wall time, completed world time is within ±1% of nominal
for every render schedule (normal, deliberately slowed, one field) whenever the world cost fits
the CPU; the number of funded ticks never depends on render time; one-shot commands run exactly
once and held controls apply to every catch-up tick; pause, menus and preferences rebase the clock
without catch-up; and with the option off the original bytes remain. Bound the debt (Red Baron:
1 s of world time) and count dropped time in VERIFY. Record the residual state differences between
quanta or CPUs instead of demanding byte identity, and leave the feel to the user's play-test.

See [simulation and presentation](simulation-and-presentation.md) for replay-specific
snapshots, native-rate prediction, load-address controls in state comparisons, and the
units/precision audit needed before reducing the simulation timestep.

A slowed renderer is easy to get when you are testing a replacement anyway: BH's full-frame c2p
experiment made each frame take 8.7 instead of ~5 fields, and the state comparison at an equal
frame number is the coupling test (Battlehawks `STATE_ONLY=1` + `compare_state.py`). Compare
before the first scripted input, or the input lands on different frames.

Write the verdict, evidence and possible designs in local `docs/open-work.md`. Follow the
user’s authorized scope; ask for a choice when designs materially change gameplay or intent.
Routine setup and validation can continue while a design decision is pending.

### Before replacing a c2p, measure the change rate

A *delta* c2p (compare with the previous chunky frame, convert only changed longs) wins when
little changes. BH: 1 % of the view changes in level flight and up to 13 % in a roll; the
compare is 31 cycles per long, the conversion 382 per changed long. A full-frame merge c2p in
Kalms' style cost 634,000 cycles per frame against 117,000 and dropped the A500 from 9.7 to
5.7 fps. Kalms' routines take a byte per pixel; for nibble-packed chunky, search the exchange
plan (six steps for BH's nibble order) and check the assembly against the game's routine in an
interpreter before booting. Battlehawks `docs/c2p.md`, `tools/c2p_stats.py`.

## 10. Building and gating patches

- **Build the authoritative fork source in place**, with outputs in the local harness's
  `tmp/build/`: `tools/build.sh [NAME] [-DDEFINE=1 ...]` writes
  `tmp/build/Indianapolis500[-NAME].Slave` and always assembles, so a define never leaves a
  stale variant. Upstream has no build file for any game; do not add one to the repository.
- vasm's `-m68000 -pic -x -devpac -Fhunkexe -nosym`, with `Games/`, the shared WHDLoad 20.0
  `Include/` and the NDK (`~/.local/opt/m68k-amiga-elf/sys-include`) on the include path. vasm
  finds `WHDLoad.i` through `-I`; StingRay's `INCDIR SOURCES:INCLUDE/` line stays. Record the
  actual dependency versions, flags and paths in local notes. Do not vendor SDK files into the
  fork.
- First rebuild the **unmodified** source and compare boot, gameplay and fixed-window state
  with the shipped slave. Indianapolis 500's cross-build differs from the shipped slave in two
  harmless words (vasm encodes `cmp` for `cmpi` and pads the hunk with `nop` instead of
  `$5678`) and behaves identically (checked in the standalone project). Keep a dependency
  change distinct from game optimizations and validate it before relying on a new baseline.
- Keep the slave's `ws_Version` (17 for Indianapolis 500, because of `ws_config`) unless a newly
  used API, patch command or header field requires more. Change the header and the ReadMe's
  requirements together when needed; test the stated minimum runtime and WHDLoad 20.0. Keep
  normal and diagnostic outputs separate.
- Gate every change behind a `CUSTOMn` bit and declare it in `ws_config`. With the bit off, the
  original bytes must be untouched. Write a checker that reads the local original file and
  compares those bytes at every patched range (TD2: `check_disabled.py`).
- **Compare the rebuilt slave with the shipped one by behaviour, and state what was compared.**
  A rebuild on the WHDLoad 20 KickEmu changes allocation and OS timing (Powerdrome's 68000 pit
  sequence took 387 fields instead of 195), so measure performance only with the same loader on
  both sides. Hard Drivin' compared the sequences of distinct sampled poses and stable screen
  images (functional equivalence, not per-field equality); Powerdrome compared the game bytes
  after undoing relocations, the main state block with named exceptions (RNG seed, clock samples)
  and both bitmaps outside the on-screen clock, with negative checks proving the comparator fails
  on any other byte.
- Keep instruments (fixtures, RNG pinning, slow drawing, pixel twins, assembly unit tests) in a
  **`VERIFY` build only**. Normal builds must not contain them.
- Audit hook boundaries: a `PL_PS`/`PL_PSS` must replace whole instructions, and nothing may
  branch into the replaced bytes (TD2: `audit_simulation.py`). One wrong return adjustment in
  TD2 landed two bytes early and crashed later. A sentinel unit test caught it.
- Choose the patch type deliberately. Use `PL_P` (jump, no return) when the replacement
  re-executes the original body. TD2's `PL_PS` twin returned into code that had already run and
  corrupted the stack.
- **Find self-modifying code before moving or caching code.** Powerdrome's audit decodes the
  executed instructions of a capture, evaluates each write's destination from the recorded
  registers (indexed and register-indirect as well as absolute) and intersects the written bytes
  with executed instruction bytes. It found two branch-displacement writers in the rasterizer;
  data words inside a code hunk are not self-modifying code. Its fast path replaced them with
  static specialised loops and a dispatcher that keeps the continuation in data, so drawing never
  writes code. Build generated code before the slave's final `resload_Patch` flush, or flush after
  it ([Hardware debugging](new-game-playbook-hardware.md)), and leave cache selection to
  WHDLoad's `CACHE`/`DCACHE` options.
- Reading `SR` is privileged on the 68010 and later. A hook that may run in user mode saves the
  condition codes with `MOVE CCR` there (it doesn't exist on the 68000) (Powerdrome).
- **Give the game the entry registers its contract promises.** Powerdrome's loader jumped into the
  DOS program with the `a0`/`d0` that `resload_Patch` may destroy; the game dereferenced them as
  its command line, and only an MMU boot exposed it. Pass a valid empty command line (`a0` → a
  newline, `d0` = 0).
- Gate per-CPU behaviour on `WHDLTAG_ATTNFLAGS_GET`, read before `resload_PatchSeg`, or on
  exec's `AttnFlags`. TFH ships a 68000 and a 68020 version of each maths routine (`mulu.l`/`divu.l`
  where the original paired 16×16 operations give identical bits) and picks one at patch time;
  assemble them in `MACHINE 68020`/`68000` sections.
- **Gate on memory too, and measure the slow machines.** A feature that helps a fast CPU can
  slow a chip-only machine: I500's CPU drawing cost 10–20% on the A500 and 5–15% on a stock
  A1200. Its single option works only on a 68020+ with hunk 0 in fast RAM (not chip below
  `$200000`, not slow RAM at `$C00000–$DFFFFF`), and the A500 and stock A1200 then run exactly
  the original. Prefer one player-facing toggle and keep manual values for tooling unlisted.
  Whether it defaults on is the user's call: I500's is off; TFH and Red Baron turned theirs on,
  with the original game one switch away, because faster rendering, frame pacing and real-time
  simulation only behave as intended together (TFH).
- **Check what spills into chip RAM when the expansion pool fills.** Red Baron's 512 KB ExpMem had
  24 bytes free, so the game's `MEMF_ANY` blocks landed in chip. A VERIFY-only census through the
  KickEmu `AllocMem` vector listed every spilled block; once no DMA was found touching them,
  raising the slave's fast-memory size to the measured peak plus headroom gained 4–13% on the
  68020 to 68060. Check that the minimum A500 configuration still boots, update the ReadMe's
  memory line, and keep DMA data in chip.
- **Draw in fast RAM, copy to chip** on a 68020+ with real fast RAM (Powerdrome): copy the
  rasterizer into fast RAM along with a staging bitmap, draw the scene there, then wait for the
  display handshake immediately before a `MOVEM` copy of the drawn rows into the chip back buffer,
  so the wait overlaps fast-RAM drawing. The code fetch was the win: the bitmap alone gained
  nothing on the 68020, bitmap and code took it from 15.7 to 22.2 fps, a 68040/25 from 17.9 to
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
  mode alone. Indianapolis 500 measured no gain and a corrupted display was reported. Treat it as
  an option-gated candidate: check the picture, and expect most from games with five or more
  lores planes whose CPU or blitter waits on chip RAM.
- **Pixel twins for renderer replacements** (I500 `pixel_verify.s`): the VERIFY build runs the
  new code into a guarded shadow bitmap, then the native code into the real one, and compares
  every plane plus the registers that survive, including X. Twin the replaced inner loop, not the
  whole function: callers may enter partway with their own state (I500's dither phase). The stub
  ignores memory writes, so select fixtures at boot with `CUSTOMn`, never through gdb. A
  framebuffer twin cannot show a display-fetch problem: check those on screen.
- **Check every replaced routine against a model of the original, in the emulator** (TFH
  `xform_check.py`, `c2p_check.py`): write a Python model of the original routine and check it
  against the original's own calls first; then, in the VERIFY build's fixed window, break at the
  replacement's entry and exit for N calls, dump inputs and outputs, and compare with the model.
  Do it on the A500-eq (68000 code) and a 68020 (68020 code). Include the edge cases the model
  shows (negative operands in sign-magnitude maths). This is cheaper and stronger than state
  comparisons, which only show that a scene looks the same.
- **Declare every hook range where it is installed** (LoV: a `PERF_RANGE hN:OFFSET LEN bit=B`
  comment beside each patch), so the disabled-bytes checker reads its list from the source and
  can't drift from it.
- **Keep the original code on a CPU where the replacement doesn't measure better.** LoV's wall
  unroll, sprite rows and reciprocal cache helped the 68000 but regressed or did nothing on the
  68020, so 68020+ keep the original bytes; VERIFY can still force each body on either CPU for
  its twin. A release build may force all verified performance bits on and expose only the
  player-facing options, while a `DEVELOPER` build keeps the individual switches for A/B work.
- **Kalms c2p** (shared checkout `~/.local/share/amiga/kalms-c2p`; vendor the files you use with
  a README listing every local change): for 16 colours, `bitmap/c2p1x1_4_c5_bm_word.s` on
  68000/10 and `bitmap/c2p1x1_4_c5_bm.s` on 68020+. They need widths that are multiples of 32.
  For narrower views convert an **enclosing window** from a staging buffer padded with colour 0,
  and save and restore the extra destination bytes around the conversion: after a view switch
  they can still hold the previous view's pixels (LoV's first medium-view twin caught this). Make
  the pixel twin perturb the bits the game leaves undefined (LoV's low nibble), so a wrong merge
  can't hide.

## 11. Measuring an improvement

- A/B **only** with `fixed_window.sh`, same build, the option on vs off. The fps figures come
  from swap counts. Script the whole pair (LoV `tools/ab_window.sh PREFIX OFF ON [ROUTES
  [MACHINES]]`: both machines, both routes, one capture at a time, then the analysis chain on
  each capture; `tools/ab_summary.py PREFIX` tabulates them and writes off/on first/last
  comparison sheets). Delete each 0.5–1 GB trace once its reports exist (`KEEP_TRACE=0`): a
  deterministic window can be recaptured.
- When game time depends on frame time, the faster build reaches the anchor in a different
  scene. Quote fps, but judge the routine by **cycles per completed call** (boundary-partial calls
  excluded, main task separated from interrupts), and add a scene-stable route (LoV: stop facing
  a wall, wait, then anchor). Physics and state correctness come from per-field state comparisons, never
  from screenshots.
- Skip anything worth under 3% of a frame unless it's free. Bound a candidate's cost by summing
  its instructions' cycles before writing it. An fps window cannot even resolve the sign of a
  change under about 2% (Red Baron): bound such changes statically, and drop any step that
  measures under 2% on every CPU class once implemented.
- Re-run the fast-CPU configurations. A change can help the A500 and do nothing on a chip-bus
  bound 68030, or the reverse. TD2's renderer hits a 25 fps chip-bus ceiling at any CPU speed.
- **A faster CPU does not make chip RAM faster.** On AGA the CPU's 32-bit chip stores beat the
  16-bit blitter for fills (no reads), but the blitter wins chip-to-chip copies (I500: textured
  rows by CPU dropped a heavy view from 24.0 to 20.4 fps). A 68040 at 25 or 40 MHz gave I500's
  heavy views the same 25.0 fps: they are bound by chip RAM and the blitter. Red Baron's cached
  68030 at 200 MHz still drew 12 fps, and Stellar 7's 68060/50 gained 0.3 fps over a 68040/25.
- **Blitter priority (`BLTPRI`) helps when the CPU polls the blitter.** TD2 sets it while the game
  runs and restores it on exit, so the CPU's `DMACONR` polls stop taking blitter slots: A500 5.2 →
  5.4, A1200 16.1 → 16.7, 68020/100 21.1 → 25.0 fps. I500 measured no effect. It disturbs the
  68020 cycle trace: use `SWAP_ONLY` for fps when it is on.
- **Spend measurement on decisions.** Red Baron's agent made 209 commits in three days; the last
  132 did not change the player build, and 81 of the last 100 were verification or measurement.
  4D Sports Driving and Powerdrome stalled the same way. Give each feature a fixed budget: build
  every mode; run the host tests and the hook audit; one same-build A/B window per affected CPU
  class (≥2,000 fields, or 1,000 of steady play on the A500); one native twin for an exact-output
  replacement; two or three deliberate sabotages for any new checker. Run the full machine matrix
  only at checkpoints, never rerun the emulator without a source change in between, and open a
  work item only for a demonstrated defect.

## 12. "Ready to improve": the definition of done for setup

- [ ] Existing worktree/branch, the local `AGENTS.md` and the repository-local identity
      respected; local harness ignored; staged changes contain no new game bytes or generated output.
- [ ] Game, version, slave type and existing patches documented.
- [ ] `td2_report.py` names every hot region; traces have PCs.
- [ ] A fixed gameplay window that is reproducible across boots: same screenshots, same state.
- [ ] A validated frame counter: full trace and `SWAP_ONLY` agree.
- [ ] A baseline on the machine matrix (§8), with a profile on at least the A500-equivalent and a
      68020, each machine's cache state, and the commands that reproduce it.
- [ ] No new host-specific paths in the upstream diff; shared files through §1 variables.
- [ ] Fork source is authoritative; the harness builds that source with documented dependencies.
- [ ] Changes are confined to the target game; other games and shared build settings are untouched.
- [ ] The game-time model: time sources, state map, coupling test results.
- [ ] Local `docs/open-work.md` lists ordered work items and any unresolved design decisions.
- [ ] A rebuilt, unmodified slave that behaves identically, with CUSTOM gating and a VERIFY
      build ready to receive patches.

Effort, for planning: on I500, everything except the state map, the coupling test and the CUSTOM
gating took one session. On BH, one session reached a reproducible-timing fixed window and an
A500 baseline, including the slave reconstruction, the KickEmu rebase and the input tape; the
68020 baseline and the game-time model were left for the next. BH's capture is one boot (~4
minutes: ~4600 fields of menus in warp). A 100-field fixed-window capture takes about 2 minutes (calibration boot
plus measurement boot) and about 520 MB.

## 13. Contribution and release archives

The deliverable is a focused source change on the game branch in the Vesuri fork, plus a
message to StingRay proposing it. Upstream does not work through pull requests: every commit
there is StingRay's own upload, and he releases on whdload.de with his own installer archive.
Do not open a pull request or contact him unless the user asks; the user sends the message.

Review `git diff --stat master...HEAD` and the staged diff separately (the former excludes
uncommitted work). Keep only the game's source files (`Games/Indianapolis500_WHD.s` and
`Games/Indianapolis500_*.s`). Preserve upstream encoding, line endings, filename case, notices,
credits and unrelated bytes. Do not import the harness, docs, tools or SDK. Use explicit paths
when staging; check new files against ignore rules.

Describe the change in StingRay's history block at the top of the source, newest first, in his
format (`; dd-Mon-yyyy<TAB>- text`, continuation lines indented by tabs), and propose a version
in the `.info` string. The version number and the wording are StingRay's call: say so in the
message. New features need an explicit off path (Indianapolis 500's option is off by default).
Player-facing text (the ReadMe, icons and their tooltypes) lives in the installer archive, not
in the repository: propose those with a release archive, and treat an icon that enables an
option as an intentional player-facing change.

When release packaging is requested, adapt TD2's `tools/package_release.py` in the local
harness. Build from `$GAME_SOURCE`, stage below its ignored `tmp/`, and write archives to its
ignored `dist/`. Use LHa for UNIX (`LHA`, §1), level-1 LH5 headers (`lha a1o5q2`).

- Retain the original installer and preinstalled archives as immutable local inputs.
- Replace the normal release slave and ReadMe; change icons only when intended. The installer's
  `Source/` must include the updated slave and all new modules, so it assembles as shipped.
  Include redistributable public-domain SDK sources/headers with provenance only when making a
  self-contained source archive, without committing that SDK into the fork.
- Validate an explicit member manifest: unchanged names/case/content except the planned files
  and added source files. TD2's packager checks sorted membership; LHa sorts members, so do not
  claim original member order is preserved.
- Re-extract and compare bytes with the staging tree; check version, requirements, tooltypes,
  and absence of VERIFY-only options/instruments. Build or validate the packaged source as well.
- The preinstalled archive contains copyrighted game data: keep it local. Do not add it to Git
  or publish it as a source release. Inspect installer contents before publishing them too.
- Preserve beta status until play-testing is complete. Record measurements and remaining
  limitations in the local notes, with concise reproducible validation in the message.

Push or open a pull request only within the user's authorized scope, using **Vesuri**. Verify
base/target and the complete diff first. No publishing is implied by creating this playbook.

### Indianapolis 500 port (2026-10-09)

- The fork's unmodified `Games/Indianapolis500_WHD.s` equals the installer's `Source/` copy, and
  its vasm build equals the standalone project's recipe (two words from the shipped slave, §10).
- Commit `8a24565` ports the standalone project's slave (its commit `e67afb0`): the main source
  plus eight modules renamed `Indianapolis500_<Module>.s`. Every variant (normal, `VERIFY`,
  `DRIVING_TEST=1` and `2`, `TIMING`, `SOFT_TIMING`, `DRIVING_TEST` with `VERIFY`) builds
  byte-identical to the standalone project's builds. Only comments changed (local doc and tool
  paths removed), and two upstream lines that the standalone copy had altered were restored (the
  banner's Latin-1 byte and the `d7` comment).
- The harness in `tmp/dev/` is the standalone project's with paths adapted; commands are in
  `tmp/dev/docs/profiling.md`. Work continues from `tmp/dev/docs/open-work.md`.
- Indianapolis 500's 3.1b contribution includes extrapolation only while driving, moving
  cars in instant replays and paced replay wipes; `CUSTOM2` was removed. The contribution
  is [StingRay PR #2](https://github.com/MK1Roxxor/WHDLoad_Patches/pull/2).
