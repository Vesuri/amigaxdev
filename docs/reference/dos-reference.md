# The DOS reference under DOSBox-X

How a DOS port runs its original as ground truth: a pinned, patched DOSBox-X that installs
the game with its own installer and then runs it headless, deterministically and traced to
named milestones. The playbook's [§4](../playbooks/new-port-playbook.md#4-build-the-reference-loop-first)
says why the loop comes first; [validation harness](validation-harness.md) holds the general
method. The x86 facts the translator and its oracles need are in [x86 real mode](x86-real-mode.md).

AmigaXDev installs stock `dosbox-x` and `dosbox-staging` (`Brewfile.extras`) for manual play
and comparisons. Reference runs use the project's own patched build; the shared environment
has no patched build or shared patch set yet ([open work](../open-work.md)).

## The emulator build

- **Pin it by commit**, not only by tag, in the project's `manifest/` (a tag can move). The
  ports so far use tag `dosbox-x-v2026.08.31`, commit `4f19017c5f565dc40d01fede0f1382892e7243d7`.
- **Build outside the repo** when the repo path contains a space (game names do): autoconf
  fails on it. Keep the tree under `~/.local/src/<project>-dosbox-x` and link it from the
  ignored `tools/vendor/dosbox-x`.
- Configure with `--enable-debug=heavy --enable-sdl2`. The heavy debugger is what a live
  single-step oracle needs. If the default macOS SDK fails to link (`ld: tapi error`), set
  `SDKROOT` to the previous SDK under `/Library/Developer/CommandLineTools/SDKs/`.
- **Check the tree before every run**: HEAD is the pinned commit; every file the patch
  series touches equals the series applied to that commit (applied in a scratch index); no
  other tracked file changed; the binary is newer than every patched file. A stale binary
  or an unrecorded edit otherwise produces a reference that nobody can rebuild.
- Apply the patches in one recorded order (`tools/patches/ORDER`), with `*.patch -text` in
  `.gitattributes`. Keep generic patches separate from the game's own, and rename only the
  environment-variable prefix when copying them from another port.
- A second, unpatched heavy-debug build of the same commit is the tie-breaker oracle where
  Unicorn deviates ([x86 real mode](x86-real-mode.md#unicorn-x86-16-as-an-oracle)). Never
  use it for reference runs.

## The patch set

Each is small and does one thing. The generic ones:

| Patch | Does |
|---|---|
| trace | arms at the first instruction of the MZ entry; attributes every paragraph to the module whose bytes the last DOS read put there (works for any loader); writes executed-instruction bitmaps, edges, interrupt, port and VGA aggregates, code writes, file events and snapshots |
| trace, services option | logs every software interrupt the guest's own code raises, with all registers and FLAGS at entry (`svc`) and at its return (`svc_ret`): the oracle for the runtime's DOS, BIOS, EMS and mouse services |
| read-data | keeps the bytes of every DOS read (`reads.bin`) for the image proof |
| time-limit | ends the run cleanly at an emulated deadline. DOSBox-X writes its outputs from `atexit`, so a run killed from outside loses them |
| date, host-clock | pin the DOS date and the host file clock at arming (below) |
| trace keys option, mouse, joystick, key-chords | input on guest-instruction visits (below), modifier chords |
| release-visits | times key releases by visits too |
| rep-chunks | records where DOSBox-X cuts a REP at the end of its cycle slice, so a host run can cut at the same iteration |
| irq0-backlog | keeps an IRQ0 that the test sync gate holds back, and raises it at the next opening, instead of merging it with the next edge |
| sound | logs OPL writes with emulated time, and Sound Blaster DSP and DMA traffic |

Patches added when a game needs them:

| Patch | Need |
|---|---|
| script | an installer or front end driven by a script that waits on emulated time, the 80×25 text screen or the BIOS video mode (`0040:0049`), then presses keys, swaps floppy images, takes shots or dumps VGA state, ticked once per emulated millisecond |
| retrace | records the guest's reads of 3DAh as runs of one value per service interval, so a host run answers its own reads the same way |
| key-wait | a blocking key read at a poll point (INT 21h AH=01h/07h/08h, INT 16h AH=00h/10h): with the sync gate on, no poll point inside the read lets IRQ1 in, so the key is pressed before the call and the call waits for it |
| watch | logs the guest's reads of an interrupt-vector-table byte, for games that read the IVT as data |
| idle-irq | opens the interrupt gate during the INT 28h idle HLT that DOS console input runs, or a `getch` stalls every interrupt |
| module mapping | maps modules the guest loads with INT 21h AX=4B03: DOSBox-X reads those files itself, so the guest never issues the DOS read the trace attributes bytes by |
| overlay events | the game's own overlay manager: its call, load and return events |

## The machine

- **A 386 normal core at fixed cycles** for every reference run (`core=normal`,
  `cputype=386`, `cycles=fixed N`), whatever CPU the game asks for. A 286 personality
  differs only where interrupts arrive and in PUSHF's bits 12–15, which reach RAM when a
  manager saves FLAGS (7202h on one, 0202h on the other); use it only as a second
  personality. Choose N once, early: visit counts do not transfer across cycle settings.
- `turbo` removes only the real-time throttle; runs stay deterministic.
- Memory, EMS and XMS as the game's minimum machine asks; the machine shape also decides
  which sound driver the game loads.
- `nosound=true` mutes the host but still emulates the devices. **Never `-silent`**: it also
  sets the Sound Blaster type to none. `quit warning = false` avoids a macOS dialog.
- Headless: `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`, `-nogui -nomenu -fastlaunch
  -time-limit`.
- **DOSBox-X ignores SIGTERM.** Record its pid in the run directory and stop only that pid
  through the shared `fsuae_kill_recorded` (`$FSUAE_COMMON`), never by name.

## Install and configure with the original installer

- The oracle is the tree the original installer writes ([playbook §3](../playbooks/new-port-playbook.md#3-extract-the-original-data)).
  Extract the user's images from their archive into `tmp/`, check each against the
  manifest, make them read-only, and run the installer from fresh copies.
- Mount every floppy image on A: and swap by script. When no file name repeats across the
  disks and every volume label is equal, one union directory can serve as A: with no swaps.
- **Never `autotype`.** It sleeps in host wall time, and keys were lost or arrived early.
  Drive the installer with the script patch, waiting on screen state and emulated time.
- Success comes only from a positive marker: the script's DONE line, or a batch line after
  the installer exits that writes a marker file. A time limit or an emulator exit is never
  success. Then the installed tree must equal its manifest, and a second independent
  install must hash the same. Keep a negative control (a launch from the wrong directory,
  a missing disk) that fails.
- Unpacking is CPU-bound: give it `cycles=max` or `turbo` and a generous emulated limit.
- **The configuration is a separate step.** An installer may write no configuration until
  its setup menu runs, and without one a game can load no sound driver and stay silent.
  Run the configure step on the reference machine and pin its output files separately.
- Some games must start from their own directory (`cd \GAME` then `GAME`); a launch from
  elsewhere can fail to open its resources and return to DOS.
- macOS `openrsync` ignores `--chmod`: make each disposable copy writable explicitly.

## Runs

- Each run gets a new directory and a fresh copy of the configured tree. Exit status is
  distinct per reason: 0 the named milestone was reached, 2 time limit, 3 guest fault
  (INT 0 or INT 6), 4 emulator failure or host deadline.
- Addresses in every output are `(module, offset)`: the root by its load-image offset, an
  overlay or driver by the offset in its file or image, `-` for unowned memory (BIOS, DOS,
  emulator callbacks). Never an emulator linear address.
- Snapshots hold `ram.bin` (1 MiB, with the EMS frame read through its mapped pages),
  `vram.bin`, `dac.bin`, the registers, residency, and `writes.csv` (the last CPU writer of
  every module-owned byte since its load). DOSBox-X stores chained mode-13h byte `a` at
  `vram[((a & ~3) << 2) | (a & 3)]`.
- Event logs grow fast: a mouse polled in a busy loop can be 200,000 calls an emulated
  second. Compress the event log as it is written.

## Input

- **Trigger every input on the Nth visit of a guest instruction**, counted from the
  previous key's release: a poll site such as the game's `kbhit`, its INT 33h AX=3 mouse poll
  or its once-per-frame call. Hold keys for a fixed number of instructions. Snapshots use
  the same `name@MODULE+HEX#N` form. Alias the poll sites by name (`menu`, `frame`).
- Menus that poll every few fields drop short presses; a key held past the emulated
  keyboard's typematic delay repeats.
- DOSBox-X's mouse does not count like a real one: in mode 13h horizontal mickeys count
  double, and vertical motion has its own ratio. Measure the ratio from a snapshot, and give
  the port's INT 33h the reference's semantics.

## Determinism

- At arming, pin the BIOS tick count (which fixes DOS time, INT 1Ah and any RNG seeded from
  them), the DOS date and the host file clock. They are separate inputs: DOSBox uses DOS
  time on write-close and the host file clock on creation and on write-seek-close. Record
  both with the run.
- **The run name's length reaches the guest** (the path is in its environment): compare
  only runs whose names have equal length; references keep a fixed prefix.
- Without a sync gate, where interrupts land varies with host scheduling while the state at
  a milestone does not: trigger milestones on guest-handler entry counts or code visits,
  and report instruction counts without comparing them. With the gate (hardware interrupts
  taken only at the translator's sync points, plus irq0-backlog) a run repeats to the
  instruction.
- **The sync set keeps loop heads.** Deferring ticks to fewer points (only where the
  interrupt handler's footprint allows) moved the original's own trajectory: one demo run
  took 2.05 G instructions instead of 349 M. Fix the sync set before recording long
  references, and record its fingerprint (`polls=`) with every re-recording: each change
  re-records all of them.
- Copy-protection questions depend on the clock and on when the key arrives. Under the
  pinned clock and visit triggers every run asks the same question; answer it from the
  script and keep a wrong-answer control. A bypass is an owner decision with its own oracle
  at the screen's return, and later references are recorded with the same bypass applied in
  the reference at the same call, because the game reads state the skipped screen leaves.
- The game's own debug switches (found in its argument parser) can shorten deterministic
  routes without patching it.

## Milestones and the image proof

- A table (`reference/milestones.csv`): name, the milestone it continues from, time limit,
  keys, snapshots, the modules that must be resident, the video mode, a frame relation and
  any files to pin. A milestone's keys are its predecessor's followed by its own.
- Checks per milestone: every snapshot reached; residency and mode as listed; consecutive
  snapshots differ; the image proof holds on every snapshot; the frame relation holds
  (`=NAME`, `!=NAME@rect`); every `svc` has its `svc_ret` except those still pending; RAM,
  VRAM and DAC equal their pins.
- **The image proof**: rebuild every resident row from the files and the loader model
  (MZ load image and relocations, overlays, drivers). Every byte must equal the model, or
  have a CPU writer since its load, or be the byte the last DOS read put there. Until it
  holds, every address derived from the files is provisional.
- Pin in one invocation and reproduce in a second. Exclude text-mode VRAM: DOSBox-X's own
  messages name the run directory.
- Before the release, exit to DOS, saving and loading, and every input device the port
  supports are milestones too.
- A file the owner supplies (a recorded film, a save) can seed a milestone: pin it, and
  place it beside the installation with one fixed modification time in every harness
  ([behaviour against the reference](validation-harness.md#9-behaviour-against-the-reference)).
