# Playbook: improving a game in JOTD’s WHDLoad slave repository

For an existing project, read only the section needed for the current task. Use the
[task index](../index.md) for focused references and shared helpers. Read §0 when
starting a new project; follow the complete workflow only when setting one up.

> `$PROJECTS` below is the directory that holds the project checkouts (AmigaXDev's parent) and
> `$ARCHIVES` the directory with the game archives the user supplies. Neither is ever written
> into a repo. `<L>/<Game>` is the game's directory in the fork (its initial letter, then the
> game's name) and `<Game>HD.s` its slave source.

> **For an agent working directly in a game branch of the Vesuri fork of JOTD’s
> `jotd_whdload_slaves` repository.** Start from the existing slave source, not an empty
> repository. Keep the profiling and correctness workflow below, but make the fork’s
> `<L>/<Game>/usr/source/` the single authoritative source tree.
>
> Adapted from `new-game-playbook.md`. A focused game change touches only the game's
> directory: the slave, any new assembly/include files, the Windows makefile dependencies, the
> ReadMe and an icon when intended. It does **not** import a standalone harness, docs or a
> vendored SDK.
>
> Each game branch lives in its own worktree, created from `master`. The main checkout at
> `$PROJECTS/jotd_whdload_slaves` stays on its own branch. A game keeps its harness and docs in
> the worktree's ignored `tmp/dev/`, with at most a current plan tracked beside the slave
> source. Do not recreate an existing branch, switch the main checkout, cherry-pick another
> game's implementation, or initialize a new repo.

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
an existing baseline. Inspect a pre-existing extraction instead of extracting over it. Record
the archive's SHA-256 and file count in the local development notes.

For a **new** archive, use this procedure from the harness root after checking its listing
for unexpected absolute paths, parent-directory components or links. Substitute its names:

```sh
# Example inputs; never re-run extraction over a prepared baseline.
DOWNLOAD="$ARCHIVES/Game_v1.0.lha"
ARCHIVE_NAME=Game_v1.0.lha
ARCHIVE_ID=Game_v1.0
INSTALLED_DRAWER=Game
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

Set these defaults in the local harness (resolve `HARNESS_ROOT` from the script,
not the caller’s current directory):

```sh
GAME="${GAME:-$HARNESS_ROOT/tmp/game/Game_v1.0/Game}"
SLAVE_NAME=Game.slave
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
`WHDLoad Game.slave PRELOAD ...`; a slave's `slv_CurrentDir` may select `data` itself.
Keep Kickstart images and RTBs in runtime `DH0:devs/Kickstarts`, using §1 shared inputs.
Start the startup-sequence with `FailAt 999` and create `DH0:devs` even for a direct slave that
needs no Kickstart: a failing `Assign DEVS: DH0:devs` before `FailAt` ends the script at a
`1>` prompt.

From the harness root, once the runner and builds exist:

```sh
# Shipped baseline, even if the parent shell exported a SLAVE override:
SLAVE= amiga/run.sh
# Rebuilt development slave, with the same game data:
SLAVE="$PWD/tmp/build/Game.slave" amiga/run.sh
# VERIFY build (options depend on the instruments actually implemented):
SLAVE="$PWD/tmp/build/Game-verify.slave" amiga/run.sh
```

These are the runner interface to implement. If the runner changes into `amiga/` early,
resolve relative `SLAVE`/`GAME` first rather than relying on the caller happening to use
absolute paths.

Follow the [runtime-state policy](new-game-playbook.md#archive-layout-and-runtime-state)
for saves, fixture promotion and matched A/B inputs.

**Check:** shipped and rebuilt slaves boot from disposable copies; baseline hashes remain
unchanged and generated files stay ignored. Complete the boot/build gates in §4 and §10.

There are two kinds of archive. Work out which one you have:

Distinguish [preinstalled and installer archives](new-game-playbook.md#archive-types).

The fork already supplies the slave source at `<L>/<Game>/usr/source/<Game>HD.s`.
Inspect that first; the installer archive is useful for a shipped slave and packaging baseline,
not as a second editable source tree. If installed data or original disk images are missing,
identify the required inputs and ask for them. Do not reconstruct a slave whose source exists.
Compare the repository version and shipped slave before attributing behaviour differences to
new patches. Keep hashes and archive provenance in local development notes.

Set `GAME` to the installed drawer under `tmp/game/<archive-stem>/` as above; `run.sh`
mounts a disposable copy on `DH1:`, never the baseline itself.

Follow [slave and game-code identification](new-game-playbook.md#identify-the-slave-and-game-code)
before booting. Record the results in this harness’s game/internals documentation. Read the
slave's header and options against the installed data: distinguish game allocations from total
KickEmu/WHDLoad/preload requirements rather than sizing the machine from one constant. A
LoadSeg callback may recognise several executables (a launcher, menus, the game proper), each
with its own patch variants and signature offsets: map each loaded executable and its lifetime
separately, and do not profile only the launcher or assume they share a code/data base. Record
which supported versions are actually available; unsupported versions must be stated, and new
patches must leave other variants unchanged.

## 3. Set up local tooling around the existing game source

Use the game's existing worktree. Run these inspections there before editing anything:

```sh
cd "$PROJECTS/<worktree>"
git status --short --branch
git worktree list
git remote -v
git log --oneline master..HEAD
```

The remote is the personal fork `git@github.com:Vesuri/jotd_whdload_slaves.git`.
Inspect any configured upstream before fetching or comparing; do not change remote topology
or publish a branch merely as part of setup. Repo-local identity settings apply to linked
worktrees; verify that no worktree or environment override changes the effective settings.

Keep the upstream-facing layout:

| Location | Purpose |
|---|---|
| `<L>/<Game>/usr/source/<Game>HD.s` | authoritative slave and patch lists |
| `<L>/<Game>/usr/source/*.s`, `*.i` | new patch modules and VERIFY-only instruments |
| `<L>/<Game>/usr/source/Makefile_windows.mak` | existing build entry; add module dependencies |
| `<L>/<Game>/usr/ReadMe`, installer/icon files | player-facing changes when needed |
| `tmp/dev/` | local harness: `amiga/`, `tools/`, `docs/`, build wrapper, inputs and outputs |

If already using a separate harness, reuse it with an explicit source-root variable instead.
Never keep two editable slave copies. Tools must read and build the source in the fork.

Add `/tmp/` to the repository’s local exclude file (resolve it with
`git rev-parse --git-path info/exclude`; do not assume `.git` is a directory). Preserve its
existing entries. Check `git check-ignore tmp/dev/probe` before creating anything. This local
exclusion is shared by the repository’s worktrees and does not change tracked `.gitignore`.
Preserve existing `AGENTS.md` (and an existing `CLAUDE.md` that imports it); add no new
`CLAUDE.md`. `AGENTS.md` points at the harness notes and the installed shared index
([a project's agent instructions](../environment.md#a-projects-agent-instructions)); keep local notes local unless their inclusion in the game’s
source contribution is deliberate. Inspect staged paths before every commit.

```sh
# From the worktree root, after verifying the exclusion:
export JOTD_ROOT="$PWD"
export GAME_SOURCE="$JOTD_ROOT/<L>/<Game>/usr/source"
mkdir -p tmp/dev/amiga tmp/dev/tools tmp/dev/docs tmp/dev/tmp/build
cd tmp/dev
# amiga/env.sh sources the shared env.sh; amiga/run.sh launches through fsuae_common.sh.
```

**Command convention for the remaining sections:** `amiga/`, `tools/`, `docs/`, `tmp/` and
`dist/` are relative to the harness root (`$JOTD_ROOT/tmp/dev`), not the Git root. Thus all
captures and local docs stay below the worktree’s ignored `tmp/`. Any `whdload/` reference
in the shared playbook means the slave source: use `$GAME_SOURCE` and explicit build outputs
under the harness `tmp/build/`; do not create a copied slave tree. Set these roots in the local
environment/build wrapper so they survive a new shell, and quote all paths (worktree names may
contain spaces). Ensure the harness keeps its own process, port and log directory; do not
accidentally resolve it to the main Git checkout.

Write only the tools the game needs, on the shared package: the gdb server is
`amigaxdev.gdbserve`, imported through a `tools/_amigaxdev.py` shim that puts `$AMIGA_PYLIB` on
`sys.path`; import `amigaxdev.barto` and `amigaxdev.env`, and run
`python3 -m amigaxdev.disasm|adf|patchlist` after `. amiga/env.sh` (AmigaXDev
`docs/environment.md`, "Shared tools"). Validate any state comparator on this game. Shared
inputs must use §1 variables. Changes intended for the fork must contain no host-specific paths.

What is generic and what is game-specific:

Use the shared [harness tools table](new-game-playbook.md#harness-tools).
Keep the fork-specific source and harness paths above.

Keep a task-based index in the local harness notes, with these current-state documents:

| Doc (relative to the harness) | Holds |
|---|---|
| `docs/open-work.md` | current status, uncertainties and ordered next items |
| `docs/development.md` | source root, build, inputs, variables, run/capture/check/release commands |
| `docs/internals.md` | executable versions, hunks, patches, display, time model and measurements |

Do not commit a standalone-project scaffold at the fork’s root. Keep the eventual game change
focused; upstream-facing explanation belongs in the game’s ReadMe and source comments, with
extra game-scoped documentation only when useful to reviewers.

## 4. First boot (windowed, real speed)

Boot the preserved shipped slave first. Also perform the unmodified-source build and baseline
comparison in §10 before adding instrumentation or game changes. Pass the selected slave
explicitly with `SLAVE`, so a harness default cannot silently run an old build.

Use the [shared procedure](new-game-playbook.md#4-first-boot-windowed-real-speed). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

## 5. Attach the debugger and get a trace with PCs in it

Use the [shared procedure](new-game-playbook.md#5-attach-the-debugger-and-get-a-trace-with-pcs-in-it). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

The first lldb attach to the x86_64 build may take minutes; that is host preparation time, not
emulated capture duration. Record consecutive `monitor profile` chunks (100/100/50 fields for a
250-field window) with no screenshot or resume between them, and retain the exact slave and
before/after RAM with the capture.

## 6. Map memory, then find a reproducible gameplay window

Use the [shared procedure](new-game-playbook.md#6-map-memory-then-find-a-reproducible-gameplay-window). Paths refer to
this game’s harness root; retain the fork layout and rules from §0–§3 above.

For a game that takes over the graphics and keyboard, an OS-task tape (`WaitTOF`, timers) stops
working after the takeover. Inject keys at the game's native polling points from a
source-owned VERIFY module, count polls instead of host time, and disable host joystick input.
Buttons may also need the key held in the game's native keyboard bitmap. A shared input routine
is called from menus and gameplay alike, so reaching it does not prove gameplay: count gameplay
steps only from the gameplay caller, after the menu tape has finished and its keys are released,
and publish that counter, the gameplay-only breakpoint address and the UI flag in a VERIFY
marker. Gameplay steps are native input calls, not validated display frames. Runtime settings
changed by a route (preferences, detail levels) stay in the disposable copy; confirm them by
reopening the screen, and never write them back to the pristine archive.

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
  `tmp/build/`. A game's `Makefile` may be a historical BASM recipe referring to `.asm`, while
  `Makefile_windows.mak` assembles the tracked `.s` and includes `../../options.mk`, which may
  not exist at that resolved location. The repository-root `options.mk` has a machine-specific
  `HDBASE` default. Inspect the include layout and use a local host build wrapper with explicit
  paths; do not rewrite shared build settings for this Mac.
- Use vasm’s `-m68000 -pic -x -devpac -Fhunkexe -nosym` as the starting flags, adapting them
  only as the existing source requires. Resolve API headers, `lvo/` and `whdload/kick13.s`
  against the shared WHDLoad 20.1 development tree and NDK (§1). If directory names differ,
  build an ignored include staging tree pointing to the official sources, not a second copy
  of the game slave; generated local LVO wrappers can map `lvo/dos.i` etc. to NDK `*_lib.i`
  files with include guards. Slaves that include WHDLoad's own sources (`savegame.s` includes
  `macros/ntypes.i`) also need `-I$AMIGA_SHARE/WHDLoad/Src`. A JOTD slave can rebuild
  byte-identical with `vasmm68k_mot -DDATETIME -I$AMIGA_SHARE/WHDLoad/Include
  -I$AMIGA_SHARE/WHDLoad/Src -I$AMIGA_SHARE/ndk/Include_I -I. -devpac -nosym -Fhunkexe -pic`.
  Record the actual dependency versions, flags and paths in local notes. Do not silently vendor
  SDK files into this fork.
- vasm 1.9 may need small compatibility changes in the game source: an explicit PC-relative
  `_resload` reference, word-sized branches to a callback's exit, and a named exit label
  (`cb_loadseg_done`) instead of a macro-local `.out`. Keep them separate from game changes.
- First rebuild the **unmodified** source and compare boot, gameplay and fixed-window state
  with the shipped slave. Different date stamps, assembler encodings and KickEmu revisions
  can prevent byte identity. Keep the dependency change distinct from game optimizations and
  validate it before relying on a new baseline. A build that reaches the menus is a startup
  smoke check, not gameplay validation or equivalence to the shipped slave.
- Use the shared 20.1 headers/KickEmu for the development build, but retain the slave's
  `slv_Version` unless a newly used API or macro requires more. `PL_IFCx` needs WHDLoad 17.2,
  so a slave that uses it declares 17; that is not a reason to bump every slave to 17 or 20.
  Change the header and ReadMe requirements together when needed; test the stated minimum
  runtime and WHDLoad 20.1. Keep normal and VERIFY outputs separate and force rebuilding
  when defines change. Update `Makefile_windows.mak` dependencies for each added module, and
  check all include files needed by an upstream build are accounted for.

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
- [ ] `game_report.py` names every hot region; traces have PCs.
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
credits and unrelated bytes. Do not import harness docs, tools, a vendored SDK or another
game's patches. Use explicit paths when staging; check new files against ignore rules. Do not
commit all of `usr/` blindly, since it may contain locally generated files.

Update `DECL_VERSION` and the game’s existing ReadMe together. Preserve JOTD’s historical
entries; add a concise entry describing user-visible changes, options and requirements.
Performance enhancements should have an explicit off path. Keep independent correctness fixes,
including music and input fixes, enabled when enhancements are disabled; an enhancement toggle
is not a request to restore every original defect. If an icon enables an option, treat
that as an intentional player-facing change and check its tooltypes (for example an
`.exoticon` changed to enable `CUSTOM2=1`). Do not change every icon variant without inspecting it.

Keep the upstream contribution easy to integrate: describe the player-visible result and how
to disable enhancements, with only limitations needed to understand the change. Keep detailed
validation reports, development notes and diagnostic fixtures in the ignored local harness;
do not add them to the PR by default. Retain source needed to build the release. Present
coherent commits rather than the experiment and measurement history; when consolidating an
existing PR, preserve that history locally and coordinate any rewrite. Do not list fixes to
our own intermediate builds as fixes to the previous public release.

When release packaging is requested, write a packaging script in the local harness. Build
from `$GAME_SOURCE`, stage below its ignored `tmp/`, and write archives to its ignored `dist/`.
Use LHa for UNIX (`LHA`, §1), level-1 LH5 headers (`lha a1o5q2`).

- Retain the original installer and preinstalled archives as immutable local inputs.
- Ship exactly the previous release's files (main playbook §13): replace the normal release
  slave and ReadMe; if the original ships the slave's source, replace it with the release source
  at the same paths; if it ships none, add none. Ask before adding files the previous release
  lacked (new modules, includes, an SDK). Change icons only when intended.
- Validate an explicit member manifest: the original names and case, with content unchanged
  except the replaced files. Check sorted membership: LHa sorts members, so do not claim
  original member order is preserved.
- Re-extract and compare bytes with the staging tree; check version, requirements, tooltypes,
  and absence of VERIFY-only options/instruments. Assemble any shipped source and compare the result with the shipped slave.
- The preinstalled archive contains copyrighted game data: keep it local. Do not add it to Git
  or publish it as a source release. Inspect installer contents before publishing them too.
- Preserve beta status until play-testing is complete. Record measurements and remaining
  limitations in the local notes, with concise reproducible validation in any contribution.

Push or open a pull request only within the user’s authorized scope, using **Vesuri**. Verify
base/target and the complete diff first. No publishing is implied by creating this playbook.
