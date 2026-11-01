# Playbook: improving a game in StingRay's WHDLoad slave repository

For an existing project, read only the section needed for the current task. Use the
[task index](../index.md) for focused references and shared helpers. Read §0 when
starting a new project; follow the complete workflow only when setting one up.

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
> the shape of a focused game change, and the standalone Indianapolis 500 project (repository
> `Vesuri/indianapolis500` on GitHub, no local checkout; its scratch analysis is in the
> worktree's `tmp/dev/tmp/standalone/`), whose harness and analysis this fork's work continues. Other
> useful references are Test Drive 2, Battlehawks 1942 (input tape), Their Finest Hour (routine
> models), Legends of Valour (state waits and A/B automation) and Red Baron (a KickEmu slave in
> the JOTD fork).
>
> Current target: branch `indianapolis500`, worktree `$PROJECTS/Indianapolis 500`,
> created from `master` at `e05698e`. The main checkout at `$PROJECTS/Stingray_WHDLoad_Patches`
> stays on `master`. Do not recreate the branch, switch the main checkout or initialize a new
> repo. The game's state and open work are in the worktree's `tmp/dev/docs/open-work.md`.
> JOTD's Indianapolis 500 slave (v2.1) is older than StingRay's v3.0 and is not the base. A first
> attempt on it was abandoned uncommitted and deleted.

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
  checkout and the worktree (no `CLAUDE.md`: Claude Code reads `AGENTS.md`), listed with `/tmp/`
  in the local exclude file.
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

Use the [shared procedure](new-game-playbook.md#1-host-prerequisites-installed-by-amigaxdev). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 2. Unpack and identify the game

First establish the ignored harness and working-directory convention in §3, then return here.
Use the same layout for every preinstalled archive:

Use the [shared archive layout](new-game-playbook.md#archive-layout-and-runtime-state),
relative to this game’s harness root.

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

Follow the [runtime-state policy](new-game-playbook.md#archive-layout-and-runtime-state)
for saves, fixture promotion and matched A/B inputs.

**Check:** shipped and rebuilt slaves boot from disposable copies; baseline hashes remain
unchanged and generated files stay ignored. Complete the boot/build gates in §4 and §10.

There are two kinds of archive. Work out which one you have:

Distinguish [preinstalled and installer archives](new-game-playbook.md#archive-types).

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

Follow [slave and game-code identification](new-game-playbook.md#identify-the-slave-and-game-code)
before booting. Indianapolis 500 records the results in `docs/game.md`; its config
label is `ws_config` (JOTD uses `slv_config`).

## 3. Set up local tooling around the existing game source

Use the existing Indianapolis 500 worktree. Run these inspections there before editing anything:

```sh
cd "$PROJECTS/Indianapolis 500"
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

`/tmp/` and `/AGENTS.md` are in the repository's local exclude file (resolve it
with `git rev-parse --git-path info/exclude`; do not assume `.git` is a directory). Preserve its
existing entries, including a `/CLAUDE.md` from an older setup. Check `git check-ignore tmp/dev/probe` before copying anything. This local
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

Use the shared [harness adaptation table](new-game-playbook.md#harness-tools-to-reuse-and-adapt).
Keep the fork-specific source and harness paths above.

Keep a task-based index in the local harness notes, with these current-state documents. For
Indianapolis 500 (in `tmp/dev/docs/`, carried over from the standalone project):

| Doc (relative to the harness) | Holds |
|---|---|
| `docs/open-work.md` | current status, uncertainties and ordered next items |
| `docs/profiling.md` | source root, build, inputs, variables, run/capture/check commands (the playbook's `development.md`) |
| `docs/game.md`, `docs/slave.md` | the game's memory, time model and renderer; the slave's options, features, hooks, verification and measurements (the playbook's `internals.md`) |
| `docs/simulation-feasibility.md` | the analysis of a faster simulation |

The local, excluded `AGENTS.md` at the worktree root carries the rules, the doc index, the
path to the installed shared index and the current state for the next agent session, after the
personal commit rules ([a project's agent instructions](../environment.md#a-projects-agent-instructions)).
Claude Code reads it directly; add no `CLAUDE.md`.

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
comparison in §10 before adding instrumentation or game changes. Pass the selected slave
explicitly with `SLAVE`; adapt donor defaults so they cannot silently run an old TD2 build.

Use the [shared procedure](new-game-playbook.md#4-first-boot-windowed-real-speed). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 5. Attach the debugger and get a trace with PCs in it

Use the [shared procedure](new-game-playbook.md#5-attach-the-debugger-and-get-a-trace-with-pcs-in-it). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 6. Map memory, then find a reproducible gameplay window

Use the [shared procedure](new-game-playbook.md#6-map-memory-then-find-a-reproducible-gameplay-window). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 7. A frame counter you can trust

Use the [shared procedure](new-game-playbook.md#7-a-frame-counter-you-can-trust). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 8. Baseline profile

Indianapolis 500 records measurements in `docs/slave.md` and commands in `docs/profiling.md`.

Use the [shared procedure](new-game-playbook.md#8-baseline-profile). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 9. Understand game time before optimising anything

Use the [shared procedure](new-game-playbook.md#9-understand-game-time-before-optimising-anything). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 10. Building and gating patches

Apply the [shared patch gates](new-game-playbook.md#10-building-and-gating-patches)
for instrumentation, hook audits, CPU/memory gating and routine validation. The
fork-specific build, source ownership and release rules below take precedence.

- **Build the authoritative fork source in place**, with outputs in the local harness's
  `tmp/build/`: `tools/build.sh [NAME] [-DDEFINE=1 ...]` writes
  `tmp/build/Indianapolis500[-NAME].Slave` and always assembles, so a define never leaves a
  stale variant. Upstream has no build file for any game; do not add one to the repository.
- vasm's `-m68000 -pic -x -devpac -Fhunkexe -nosym`, with `Games/`, the shared WHDLoad 20.1
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
  requirements together when needed; test the stated minimum runtime and WHDLoad 20.1. Keep
  normal and diagnostic outputs separate.
- Gate every change behind a `CUSTOMn` bit and declare it in `ws_config`. With the bit off, the
  original bytes must be untouched. Write a checker that reads the local original file and
  compares those bytes at every patched range (TD2: `check_disabled.py`).

## 11. Measuring an improvement

Use the [shared procedure](new-game-playbook.md#11-measuring-an-improvement). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

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
