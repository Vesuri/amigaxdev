# Playbook: improving a game in JOTD’s WHDLoad slave repository

For an existing project, read only the section needed for the current task. Use the
[task index](../index.md) for focused references and shared helpers. Read §0 when
starting a new project; follow the complete workflow only when setting one up.

> `$PROJECTS` below is the directory that holds the project checkouts (AmigaXDev's parent) and
> `$ARCHIVES` the directory with the game archives the user supplies. Neither is ever written
> into a repo.

> **For an agent working directly in a game branch of the Vesuri fork of JOTD’s
> `jotd_whdload_slaves` repository.** Start from the existing slave source, not an empty
> repository. Keep the profiling and correctness workflow below, but make the fork’s
> `<letter>/<Game>/usr/source/` the single authoritative source tree.
>
> Adapted from `new-game-playbook.md`. The integration reference is local branch `testdrive2`,
> commit `ffd6594`, based on `cd97d6c`: its eight-file change contains the slave, four new
> assembly/include files, Windows makefile dependencies, ReadMe and icon. It does **not**
> import the standalone Test Drive 2 harness, docs or vendored SDK. Inspect with
> `git diff master...testdrive2 -- T/TestDrive2/usr` and reuse the method, not its game offsets.
> The original harness remains at `$PROJECTS/Test Drive 2`; other useful references are
> Indianapolis 500 (direct game), Battlehawks 1942 (input tape), Their Finest Hour
> (routine models), and Legends of Valour (state waits and A/B automation).
>
> Game branches in progress, each in its own worktree created from `master`: `redbaron`
> (`$PROJECTS/Red Baron`, from `cd97d6c`), `4dsportsdriving` (`$PROJECTS/4D Sports Driving`, from
> `cd97d6c`) and `harddrivin` (`$PROJECTS/Hard Drivin`). Red Baron keeps its docs and tools
> tracked beside the game (`R/RedBaron/docs`, `R/RedBaron/tools`); 4D Sports Driving and Hard
> Drivin' keep their harness and docs in the worktree's ignored `tmp/dev/` and only their current
> plan tracked beside the slave source (`smooth-play-plan.md`, `PERFORMANCE_PLAN.md`). The main
> checkout at `$PROJECTS/jotd_whdload_slaves` stays on its own branch; `testdrive2` is a reference
> branch there, not the base of any game branch. Do not recreate a branch, switch the main
> checkout, cherry-pick the TD2 implementation, or initialize a new repo.
>

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

Keep the archive’s directory structure and spelling. Do not extract into the tracked game
`usr/` or `usr/source/`, flatten `data/`, or point `GAME` at `data/` itself. Determine the
installed drawer and slave filename from the archive listing; do not infer them from the
archive basename. An archive may include an outer drawer icon beside the installed drawer:
retain it in the baseline extraction, but mount the installed drawer itself as `DH1:`.
Use a separate archive-stem directory for each version. If a same-named archive has different
bytes, give it a distinct local identifier (for example a checksum suffix); never overwrite
an existing baseline. Inspect a pre-existing extraction instead of extracting over it.

For Red Baron, `$ARCHIVES/RedBaron_v2.1.lha` contains the installed drawer `RedBaron/`, with
`RedBaron.slave`, `data/baron`, `data/ps`, `data/sim` and the rest of the game, plus an outer
`RedBaron.info`. Its SHA-256 is
`ec6d74e3576bf040269f1c078a9df766a8f6e6dd94c2eb29eb5d34307b87ffe4`.
The baseline has been prepared at
`$PROJECTS/Red Baron/tmp/dev/tmp/game/RedBaron_v2.1/RedBaron` (54 extracted files in the
archive directory). The download remains untouched; the retained archive and checksum
manifests are in the adjacent `tmp/archives/` directory.

For a **new** archive, use this procedure from the harness root after checking its listing
for unexpected absolute paths, parent-directory components or links. Substitute its names:

```sh
# Example inputs; do not re-run extraction over the prepared Red Baron baseline.
DOWNLOAD="$ARCHIVES/RedBaron_v2.1.lha"
ARCHIVE_NAME=RedBaron_v2.1.lha
ARCHIVE_ID=RedBaron_v2.1
INSTALLED_DRAWER=RedBaron
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
GAME="${GAME:-$HARNESS_ROOT/tmp/game/RedBaron_v2.1/RedBaron}"
SLAVE_NAME=RedBaron.slave
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
`WHDLoad RedBaron.slave PRELOAD ...`; Red Baron’s `slv_CurrentDir` selects `data` itself.
Keep Kickstart images and RTBs in runtime `DH0:devs/Kickstarts`, using §1 shared inputs.
Start the startup-sequence with `FailAt 999` and create `DH0:devs` even for a direct slave that
needs no Kickstart: a failing `Assign DEVS: DH0:devs` before `FailAt` ends the script at a
`1>` prompt (Prince of Persia).

From the harness root, once the adapted runner and builds exist:

```sh
# Shipped baseline, even if the parent shell exported a SLAVE override:
SLAVE= amiga/run.sh
# Rebuilt development slave, with the same game data:
SLAVE="$PWD/tmp/build/RedBaron.slave" amiga/run.sh
# VERIFY build (options depend on the instruments actually implemented):
SLAVE="$PWD/tmp/build/RedBaron-verify.slave" amiga/run.sh
```

These are the runner interface to implement, not a claim that the runner or builds already
exist. TD2’s `amiga/run.sh` already implements the copy-and-replace pattern; adapt its hardcoded
slave name, root handling and data default. It changes into `amiga/` early, so fix relative
`SLAVE`/`GAME` resolution rather than relying on the caller happening to use absolute paths.

Follow the [runtime-state policy](new-game-playbook.md#archive-layout-and-runtime-state)
for saves, fixture promotion and matched A/B inputs.

**Check:** shipped and rebuilt slaves boot from disposable copies; baseline hashes remain
unchanged and generated files stay ignored. Complete the boot/build gates in §4 and §10.

There are two kinds of archive. Work out which one you have:

Distinguish [preinstalled and installer archives](new-game-playbook.md#archive-types).

The fork already supplies the slave source at `R/RedBaron/usr/source/RedBaronHD.s`.
Inspect that first; the installer archive is useful for a shipped slave and packaging baseline,
not as a second editable source tree. If installed data or original disk images are missing,
identify the required inputs and ask for them. Do not reconstruct a slave whose source exists.
Compare the repository version and shipped slave before attributing behaviour differences to
new patches. Keep hashes and archive provenance in local development notes.

Set `GAME` to the installed drawer under `tmp/game/<archive-stem>/` as above; `run.sh`
mounts a disposable copy on `DH1:`, never the baseline itself.

Follow [slave and game-code identification](new-game-playbook.md#identify-the-slave-and-game-code)
before booting. Record the results in this harness’s game/internals documentation.

## 3. Set up local tooling around the existing game source

Use the existing Red Baron worktree. Run these inspections there before editing anything:

```sh
cd "$PROJECTS/Red Baron"
git status --short --branch
git worktree list
git remote -v
git diff master...testdrive2 -- T/TestDrive2/usr
```

The remote is the personal fork `git@github.com:Vesuri/jotd_whdload_slaves.git`.
Inspect any configured upstream before fetching or comparing; do not change remote topology
or publish a branch merely as part of setup. Repo-local identity settings apply to linked
worktrees; verify that no worktree or environment override changes the effective settings.

Keep the upstream-facing layout:

| Location | Purpose |
|---|---|
| `R/RedBaron/usr/source/RedBaronHD.s` | authoritative slave and patch lists |
| `R/RedBaron/usr/source/*.s`, `*.i` | new patch modules and VERIFY-only instruments |
| `R/RedBaron/usr/source/Makefile_windows.mak` | existing build entry; add module dependencies |
| `R/RedBaron/usr/ReadMe`, installer/icon files | player-facing changes when needed |
| `tmp/dev/` | local harness: `amiga/`, `tools/`, `docs/`, build wrapper, inputs and outputs |

The ignored harness is a proposed local arrangement; TD2 kept it in its standalone project.
If already using a separate harness, reuse it with an explicit source-root variable instead.
Never keep two editable slave copies. Tools must read and build the source in the fork.

Add `/tmp/` to the repository’s local exclude file (resolve it with
`git rev-parse --git-path info/exclude`; do not assume `.git` is a directory). Preserve its
existing entries. Check `git check-ignore tmp/dev/probe` before copying anything. This local
exclusion is shared by the repository’s worktrees and does not change tracked `.gitignore`.
Preserve existing `AGENTS.md` (and an existing `CLAUDE.md` that imports it); add no new
`CLAUDE.md`. `AGENTS.md` points at the harness notes and the installed shared index
([a project's agent instructions](../environment.md#a-projects-agent-instructions)); keep local notes local unless their inclusion in the game’s
source contribution is deliberate. Inspect staged paths before every commit.

```sh
# From the worktree root, after verifying the exclusion:
export JOTD_ROOT="$PWD"
export GAME_SOURCE="$JOTD_ROOT/R/RedBaron/usr/source"
mkdir -p tmp/dev/amiga tmp/dev/tools tmp/dev/docs tmp/dev/tmp/build
cd tmp/dev
TD2="$PROJECTS/Test Drive 2"
cp "$TD2/amiga/env.sh" "$TD2/amiga/run.sh" amiga/
# Select only needed tools and their imports from TD2 or the other reference projects.
# Adapt root detection, game names, source paths and output paths before running them.
```

**Command convention for the remaining sections:** `amiga/`, `tools/`, `docs/`, `tmp/` and
`dist/` are relative to the harness root (`$JOTD_ROOT/tmp/dev`), not the Git root. Thus all
captures and local docs stay below the worktree’s ignored `tmp/`. Any `whdload/` reference
in a donor tool or example means its old source location: adapt it to `$GAME_SOURCE` and
explicit build outputs under the harness `tmp/build/`; do not create a copied slave tree.
Set these roots in the local environment/build wrapper so they survive a new shell, and quote
all paths (the worktree name contains a space). Ensure the harness keeps its own process,
port and log directory; do not accidentally resolve it to the main Git checkout.

Copy the tools you need and discard unused ones after setup. Don't copy `barto.py`, `disd.py`,
`hotspots.py`, `dis.sh`, `adf.py`, `patchlist.py` or `local_env.py` from an older repo: take
`bh.py` (the shared gdb server; rename it) and `_amigaxdev.py` (the shim that puts `$AMIGA_PYLIB`
on `sys.path`) from Battlehawks 1942, import `amigaxdev.barto` and `amigaxdev.env`, and run
`python3 -m amigaxdev.disasm|adf|patchlist` after `. amiga/env.sh` (AmigaXDev
`docs/environment.md`, "Shared tools"). Copy generic `compare_state.py` from Their Finest Hour if suitable, and
validate it on this game. Remove inherited machine paths and game assumptions. Shared inputs
must use §1 variables. Changes intended for the fork must contain no host-specific paths.

What is generic and what has to be adapted:

Use the shared [harness adaptation table](new-game-playbook.md#harness-tools-to-reuse-and-adapt).
Keep the fork-specific source and harness paths above.

Keep a task-based index in the local harness notes, with these current-state documents:

| Doc (relative to the harness) | Holds |
|---|---|
| `docs/open-work.md` | current status, uncertainties and ordered next items |
| `docs/development.md` | source root, build, inputs, variables, run/capture/check/release commands |
| `docs/internals.md` | executable versions, hunks, patches, display, time model and measurements |

Do not commit a standalone-project scaffold at the fork’s root. Keep the eventual game change
as focused as `testdrive2`; upstream-facing explanation belongs in the game’s ReadMe and
source comments, with extra game-scoped documentation only when useful to reviewers.

### Red Baron facts to verify against the installed data

At the branch baseline, `RedBaronHD.s` declares slave 2.1, WHDLoad interface 16, `kick13.s`,
`CHIPMEMSIZE=$80000`, `FASTMEMSIZE=$80000`, `CACHE`, `BOOTDOS` and `CBDOSLOADSEG`.
The ReadMe says 0.5 MB ChipMem plus 1.0 MB OtherMem: distinguish game allocations from total
KickEmu/WHDLoad/preload requirements rather than sizing the machine from one constant.
The data directory is `data`, boot executable `baron`; the LoadSeg callback also recognizes
`ps` (menus) and `sim` (flight), with three patch variants for each of the latter two.
The `sim` signature locations are `$A66A`, `$A5A8`, `$A5CC`; these identify existing variants,
not proposed instrumentation points. Map each loaded executable and its lifetime separately;
do not profile only the launcher or assume the menu and simulation share a code/data base.
Preserve the existing cache flush, keyboard, bit-test, rename and save-file handling.
Record which supported versions are actually available; unsupported test coverage must be
stated, and new patches must leave other variants unchanged. Demo availability, compiler,
frame marker, determinism and game-time model remain to be established by measurement.

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

Use the [shared procedure](new-game-playbook.md#8-baseline-profile). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 9. Understand game time before optimising anything

Use the [shared procedure](new-game-playbook.md#9-understand-game-time-before-optimising-anything). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 10. Building and gating patches

Apply the [shared patch gates](new-game-playbook.md#10-building-and-gating-patches)
for instrumentation, hook audits, CPU/memory gating and routine validation. The
fork-specific build, source ownership and release rules below take precedence.

- **Build the authoritative fork source in place**, with outputs in the local harness’s
  `tmp/build/`. Red Baron’s `Makefile` is a historical BASM recipe referring to `.asm`, while
  `Makefile_windows.mak` assembles the tracked `.s` and includes `../../options.mk` (not present
  at that resolved location in this checkout). The repository-root `options.mk` also has a
  machine-specific `HDBASE` default. Inspect the include layout and use a local host build
  wrapper with explicit paths; do not rewrite shared build settings for this Mac.
- Use vasm’s `-m68000 -pic -x -devpac -Fhunkexe -nosym` as the starting flags, adapting them
  only as the existing source requires. Resolve API headers, `lvo/` and `whdload/kick13.s`
  against the shared WHDLoad 20.1 development tree and NDK (§1). If directory names differ,
  build an ignored include staging tree pointing to the official sources, not a second copy
  of the game slave. Record the actual dependency versions, flags and paths in local notes.
  No SDK files were added by `testdrive2`; do not silently vendor them into this fork.
- First rebuild the **unmodified** source and compare boot, gameplay and fixed-window state
  with the shipped slave. Different date stamps, assembler encodings and KickEmu revisions
  can prevent byte identity. Keep the dependency change distinct from game optimizations and
  validate it before relying on a new baseline. This playbook does not claim Red Baron builds
  or runs on the proposed host setup until those checks pass.
- Use the shared 20.1 headers/KickEmu for the development build, but retain Red Baron’s
  `slv_Version = 16` unless a newly used API or macro requires more. TD2 uses interface 17
  because `PL_IFCx` needs WHDLoad 17.2; that is not a reason to bump every slave to 17 or 20.
  Change the header and ReadMe requirements together when needed; test the stated minimum
  runtime and WHDLoad 20.1. Keep normal and VERIFY outputs separate and force rebuilding
  when defines change. Update `Makefile_windows.mak` dependencies for each added module,
  following TD2, and check all include files needed by an upstream build are accounted for.

For cached disk fixtures, follow [seed identity and artifact retention](../reference/validation-harness.md#cached-boot-images-are-part-of-the-fixture).
For arithmetic ports, use [integer/FPU differentials](../reference/validation-harness.md#integer-and-fpu-replacements)
and the [020–060 instruction audit](../reference/m68k-optimisation.md#sharing-optimized-routines-across-020030040060).
Debugger-extension limits and hunk discovery are covered in
[headless FS-UAE](../reference/headless-fsuae.md#project-debugger-extensions-and-memory-discovery).

## 11. Measuring an improvement

Use the [shared procedure](new-game-playbook.md#11-measuring-an-improvement). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 12. "Ready to improve": the definition of done for setup

- [ ] Existing worktree/branch and `AGENTS.md` respected; personal identity verified; local
      harness ignored; staged changes contain no new game bytes or generated output.
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

The main deliverable is a focused source change on the game branch in the Vesuri fork.
Review `git diff --stat master...HEAD` and the staged diff separately (the former excludes
uncommitted work). Keep only the intended game’s source, build dependencies, ReadMe and any
intentional installer/icon change. Preserve upstream line endings, filename case, notices,
credits and unrelated bytes. Do not import TD2’s root docs, tools, vendored SDK or game patches.
Use explicit paths when staging; check new files against ignore rules. Do not commit all of
`usr/` blindly, since it may contain locally generated files.

Update `DECL_VERSION` and the game’s existing ReadMe together. Preserve JOTD’s historical
entries; add a concise entry describing user-visible changes, options and requirements.
Performance enhancements should have an explicit off path. Keep independent correctness fixes,
including music and input fixes, enabled when enhancements are disabled; an enhancement toggle
is not a request to restore every original defect. If an icon enables an option, treat
that as an intentional player-facing change and check its tooltypes (TD2 changed its
`.exoticon` to enable `CUSTOM2=1`). Do not change every icon variant without inspecting it.

Keep the upstream contribution easy to integrate: describe the player-visible result and how
to disable enhancements, with only limitations needed to understand the change. Keep detailed
validation reports, development notes and diagnostic fixtures in the ignored local harness;
do not add them to the PR by default. Retain source needed to build the release. Present
coherent commits rather than the experiment and measurement history; when consolidating an
existing PR, preserve that history locally and coordinate any rewrite. Do not list fixes to
our own intermediate builds as fixes to the previous public release.

When release packaging is requested, adapt TD2’s `tools/package_release.py` in the local
harness. Build from `$GAME_SOURCE`, stage below its ignored `tmp/`, and write archives to its
ignored `dist/`. Use LHa for UNIX (`LHA`, §1), level-1 LH5 headers (`lha a1o5q2`).

- Retain the original installer and preinstalled archives as immutable local inputs.
- Replace the normal release slave and ReadMe; change icons only when intended. The installer’s
  `source/` must include the updated slave, all new modules, and a usable build recipe. Include
  redistributable public-domain SDK sources/headers with provenance when making a self-contained
  source archive, without automatically committing that SDK into the fork.
- Validate an explicit member manifest: unchanged names/case/content except the planned files
  and added source dependencies. TD2’s packager checks sorted membership; LHa sorts members,
  so do not claim original member order is preserved.
- Re-extract and compare bytes with the staging tree; check version, requirements, tooltypes,
  and absence of VERIFY-only options/instruments. Build or validate the packaged source as well.
- The preinstalled archive contains copyrighted game data: keep it local. Do not add it to Git
  or publish it as a source release. Inspect installer contents before publishing them too.
- Preserve beta status until play-testing is complete. Record measurements and remaining
  limitations in the local notes, with concise reproducible validation in any contribution.

Push or open a pull request only within the user’s authorized scope, using **Vesuri**. Verify
base/target and the complete diff first. No publishing is implied by creating this playbook.

### Red Baron build and launch smoke check (2026-10-09)

The local harness now builds the fork source with `tmp/dev/tools/build.sh` and runs it with
`tmp/dev/amiga/run.sh`. From the Red Baron worktree:

```sh
tmp/dev/tools/build.sh
SLAVE="$PWD/tmp/dev/tmp/build/RedBaron.slave" tmp/dev/amiga/run.sh
```

Slaves that include WHDLoad's own sources (`savegame.s` includes `macros/ntypes.i`) also need
`-I$AMIGA_SHARE/WHDLoad/Src`. Prince of Persia's slave rebuilds byte-identical with
`vasmm68k_mot -DDATETIME -I$AMIGA_SHARE/WHDLoad/Include -I$AMIGA_SHARE/WHDLoad/Src
-I$AMIGA_SHARE/ndk/Include_I -I. -devpac -nosym -Fhunkexe -pic`.

The build uses shared WHDLoad 20.1 headers/KickEmu and `ndk/Include_I`; its generated local
LVO wrappers map `lvo/dos.i` etc. to NDK `*_lib.i` files with include guards. vasm 1.9 required
an explicit PC-relative `_resload` reference and word-sized callback exit branches. Naming
that exit `cb_loadseg_done` also avoids relying on a macro-local `.out` label. These small
compatibility changes are in the game source; the harness remains ignored.

The rebuilt slave reached the opening sequence and main menu in FS-UAE (68000, 1 MB chip,
2 MB fast, Kickstart 3.1 host, KickEmu 1.3 guest, WHDLoad 20.0). The runtime slave was compared
byte-for-byte with the build; all 54 pristine archive files retained their hashes. This is a
build/startup smoke check, not flight validation, equivalence to the shipped slave, coverage
of all game versions, or an A500-equivalent performance measurement. Menu evidence:
`tmp/dev/tmp/build/startup.png`. Debug capture uses local `tools/redbaron.py`, adapted from
TD2 with its own socket; the runner refuses a port already held by another process.


### Red Baron keyboard route and flight recognition

From the Red Baron worktree, run the ignored local harness:

```sh
python3 tmp/dev/tools/reach_flight.py --bank
```

This builds the canonical source with `VERIFY`, starts a fresh runtime copy of the
preinstalled archive, skips the scrolling credits, selects a mission, answers No to the
pre-flight mission-tape prompt, and opens F10 Preferences. It activates each detail slider
with Enter before pressing Right to its maximum, confirms it with Enter, enables Ground
Detail (ON IN COMBAT), leaves Time Scale unchanged, and selects ACCEPT. Reopening Preferences
confirmed the accepted settings (`tmp/dev/tmp/build/preferences-verified.png`). These are
runtime settings; persistence back to the pristine archive is neither intended nor claimed.
The route assumes the original archive preferences and the supported v1 executable layout.

The source-owned `tape.s` and `tape-route.i` inject keys at native polling points:
`ps:$15b3a` and `sim:$1ef92`. Return must also be held in the native keyboard bitmap to
activate buttons. OS-task WaitTOF/timer input was unsuitable after graphics takeover.
The route uses poll counts instead of host timing and disables host joystick input.

For flight recognition, `sim:$1ed82` is a shared input call, so reaching it alone is insufficient.
Only caller `sim:$21d30`, after the complete menu/preferences tape and key release, increments
the gameplay step. The live `RBVERIFY` marker contains that counter at +44, a gameplay-only
breakpoint address at +48, and the current flight/UI flag at +52. The harness stops at step 1;
`--bank` additionally holds Right at steps 20–34, releases it at 35, and captures step 40.
It saves screenshots, build/archive hashes and marker state under `tmp/dev/tmp/prof/entry`.
The emulator is left paused; resume with `python3 tmp/dev/tools/redbaron.py cont` or quit with
`python3 tmp/dev/tools/redbaron.py quit`.

This provides a flight-entry checkpoint and a visibly verified right-bank input test.
Gameplay steps are native input calls, not validated display frames. Full state determinism,
FPS counters and profiling baselines remain to be established. The tested machine remains
68000 with 1 MB chip and 2 MB fast RAM, not an A500-equivalent performance baseline.
All instrumentation is excluded from normal builds.


### Red Baron short profiling command

A 250-PAL-field (approximately five-second) flight capture and detailed analysis are now
available. From the Red Baron worktree, run:

```sh
python3 tmp/dev/tools/profile_flight.py
```

It boots the accepted maximum-detail fixture, records consecutive 100/100/50-field chunks,
retains the exact slave, records before/after RAM, and generates routine attribution plus
exact-PC/hardware metrics in a new timestamped `tmp/dev/tmp/prof/` directory. The first LLDB
attach may take minutes; that is host preparation time, not emulated capture duration.
No screenshot or resume may be inserted between chunks. The local report tools are
`redbaron_report.py`, `trace_series.py`, and `profile_metrics.py`.

The versioned analysis and expanded manual commands are in `R/RedBaron/docs/profiling.md`.
Baseline evidence is in `tmp/dev/tmp/prof/baseline`. In that short scene the bitmap reflection
routine at sim:$304d0 consumed 30.96% of cycles; geometry and audio were also significant.
The candidate presentation marker sim:$3154a writes the copper bitplane-pointer list;
its frame-rate interpretation and repeatable A/B state still need independent validation.
