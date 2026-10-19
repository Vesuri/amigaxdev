# Validation harness

How a port proves that it does what the original does. The rules come from the port
projects. Each rule names the project where it was learned. Related docs:

- [Native port validation](../native-port-validation.md): crash dumps turned into
  regressions, installer updates and release archives.
- [Measurement method](measurement-method.md): performance numbers. Most of its rules on
  verifying an instrument apply to oracles too.
- [Fixed-time simulation](../playbooks/fixed-time-simulation.md): timing departures.

1. [Ground truth](#1-ground-truth)
2. [Levels of evidence](#2-levels-of-evidence)
3. [Routine differentials](#3-routine-differentials)
4. [Fixtures: what to randomise](#4-fixtures-what-to-randomise)
5. [Results, not implementation details](#5-results-not-implementation-details)
6. [Sabotage every gate](#6-sabotage-every-gate)
7. [What a differential cannot see](#7-what-a-differential-cannot-see)
8. [Whole-program determinism](#8-whole-program-determinism)
9. [Behaviour against the reference](#9-behaviour-against-the-reference)
10. [On-target checks](#10-on-target-checks), including [the user’s route](#exercise-the-users-route-as-well-as-isolated-fixtures)
11. [Pictures](#11-pictures)
12. [The faithfulness seam and deviations](#12-the-faithfulness-seam-and-deviations)
13. [Coverage](#13-coverage)

## 1. Ground truth

**Tests, not confidence, settle correctness.** Ground truth is the original program under a
reference emulator. Never compare the port with itself or with a host approximation. A layer
cannot prove itself by agreeing with another layer derived from the same source (Slicks,
Secret Weapons of Luftwaffe, Revs, Downwell).

| Original | Reference | Project |
|---|---|---|
| BBC Micro 6502 | jsbeeb, scripted; cycle counts read from the CPU | Revs |
| Atari 8-bit 6502 | atari800 in FIFO mode, RAM dumps | Rescue on Fractalus |
| DOS x86 | DOSBox-X with in-repo trace patches; Unicorn x86-16 as the instruction oracle | Slicks, Secret Weapons of Luftwaffe |
| Classic Macintosh 68000 | MAME `mac2fdhd` with the original System | Vette, Alone in the Dark |
| 68008 arcade board | MAME footage and board evidence; a host Musashi model as the executable reference | Pokeri |
| GameMaker (Windows) | The Windows build and its VM bytecode; decompiled GML is only a readable hypothesis | Downwell |

Rules for reference runs:

- **Run the reference headless.**
  - MAME: `SDL_VIDEODRIVER=dummy`, `-window`, and explicit `-cfg_directory` and
    `-nvram_directory`, so no state leaks into the repo. `-video none` alone still opens a
    fullscreen window.
  - Bound every run with a timeout and stop only your own process (Vette).
- **Keep the reference instrumentation in the repo,** as patches to the emulator or as
  scripts in its scripting language. Record what each milestone saw (Slicks):
  - executed addresses and block entries, direct and indirect edges;
  - interrupts with their registers, port events and code-region writes;
  - file events and frame-buffer or state hashes.
- **Run two CPU personalities when the binary probes the CPU** (Slicks: 286 and 386).
- **Keep a lossless seam beside every normalised view.** That means the exact instruction
  stream, VM assembly or resource metadata next to the decompiled or transliterated form, so
  decompiler errors stay auditable (Downwell, Revs).
- **An image built from the disc does not model registers or OS-left state.** The stack
  pointer, zero page and workspace the OS hands over are provisional until measured on the
  reference (Revs: `S` inherited as `$F8`, while a zeroed global gave 0).

## 2. Levels of evidence

Each level answers a different question. None alone proves whole-game fidelity (Slicks,
Revs).

| Level | Proves | Blind to |
|---|---|---|
| Instruction semantics: random legal states in an independent oracle against the IR or generated code | Each instruction and lowering | Composition, devices, timing |
| Routine differential: twin against oracle over fixtures | One routine's contract on the host | The target, endianness if run little-endian, anything the two sides share |
| On-target in-process differential | The replacement on the real CPU, and its cost ratio | Inputs the run never produced |
| Whole-program determinism: RAM at frame N against a recorded reference | Changes that move the oracle too (generator, CPU model, memory layout) | Anything the recorded trajectories never reach |
| Behaviour against the reference: milestones, lockstep, picture comparison | The port computes what the original computes | Paths no scenario drives |
| Gameplay regression suites with explicit success records | Lifecycle paths still complete | Fidelity of what they pass through |
| Linked-ELF checks under a CPU oracle | The assembly actually linked | DMA-era timing (Pokeri) |

**Gate a change by what it can affect** (Revs, Vette):

- documentation: link and syntax checks;
- a pure helper: host checks;
- a runtime change: original-byte checks and a bounded target run;
- a release or installer change: see [native port validation](../native-port-validation.md).

## 3. Routine differentials

- **Rewrite in small byte-identical steps.** Turning a transliterated routine into clean C is a
  loop: verify the disassembly, splice the new body in by line, run the routine's differential,
  commit. One routine per commit, each independently green (Revs). The ways a green step still
  breaks at runtime are the fixture rules below: an argument in a register the fixture never
  varied, a gating byte that left a branch unexercised, a live exit register filed as incidental.
- **Fixture or fail.** A validated name with no fixture fails the run. A run with zero
  comparisons is a failure (Rescue on Fractalus printed PASS with none).
- **Compare the complete live-out**, not just memory:
  - declared live registers and flags;
  - the sequence of hardware writes, because order is semantic;
  - traps, OS calls and stack.

  A memory-only diff passed 4 of 9 sabotages of a routine that writes the video chip twenty
  times a call (Revs).
- **No "incidental difference" bucket.** Each fixture declares its live exit registers and
  flags. Declared ones are hard failures; undeclared ones are asserted dead. An "incidental"
  exit `A=0` shipped a live bug (Rescue on Fractalus). Some older docs still call exit
  register diffs fine; that rule is retired.
- **Mask undefined flags rather than canonising them** (Slicks).
- **A fast path that bypasses the traced interface must trace itself.** Otherwise the twin is
  validated on the writes it did not optimise (Revs).
- **Count unhandled traps (self-modifying-code sites, unknown calls) in both directions:**
  zero over legal cases, nonzero over illegal ones. An oracle that aborts on the first trap
  makes the path untestable.
- **Run the differential big-endian, or lint wide aliases of little-endian guest RAM.** A
  green host run with garbage on the target happened (Rescue on Fractalus, Revs).
- **Two adjacent asm twins may pass values in registers instead of through guest memory,** but
  keep the shim seam so the C oracle stays reachable through the memory path, and write down the
  precondition the callee inherits, such as which registers arrive zero-extended (Revs).
- **A shim or seam reproduces every register and flag its callers read,** transitively, even
  when the native core no longer needs it.
  - A hook seam hands over every register live at that address, not only what the default
    callee reads. A stale Y caused a months-long corruption (Revs).
  - Treat an OS call as clobbering everything its contract doesn't preserve.
  - Flags can escape a routine.
  - A trap happens at the guest instruction boundary, after the stores before it.
- **Keep the oracle independent of what is being tested.** A transliteration generated by
  the same transpiler as the twin cannot see a transpiler change. The original bytes under
  Unicorn against generated 68020 code under a second engine can (Slicks, Revs).
- **Audit the architecture, not just the output.** Reject generated code for:
  - unexpected guest-context traffic, helper calls or flag materialisations;
  - dispatcher exits.

  Count interpreter and fallback entries in production scenarios, and fail on an unexpected
  one (Slicks, Revs).

## 4. Fixtures: what to randomise

**Randomise by default.** Randomise the whole guest state, including gating bytes, and
decorrelate flags from values. Otherwise a branch stays untested because its gate happened
to be zero in every hand-written case (Rescue on Fractalus).

**The domain rule.** A fixture models the inputs the game actually uses, not every possible
input (user decision, Revs). Narrow a byte only to a representation invariant you can state:
"packed BCD", "index < 21", "pointer in this table".

- Write the invariant at the fixture, together with its writer.
- If it is ever violated at run time, the defect is in that writer.
- If no writer exists, the invariant isn't real; go back to random bytes.
- Control flow must still go both ways.
- The tell that a fixture is too wide: the harness is the only reason the twin isn't written
  the obvious way. Revs reimplemented NMOS decimal `ADC` in software before narrowing to
  valid BCD let one `ABCD` do it.

**A random pre-state can be systematically degenerate** (Revs):

- A random self-modified byte in a callee can hang the oracle (a branch to itself) or exit at
  once and starve the routine under test. Plant the original's bytes at the callee's sites.
- Uniform bytes are not boundary coverage. Draw boundary values explicitly, and hold a gating
  cell in its interesting range for a third of the cases.
- An equality against a computed value is reached about once in 256 cases. Add explicit
  equality, wrap, `$FFFF` and zero-count cases.
- A callee can loop forever on states the real tables never produce. Exclude them, and say
  why at the point of exclusion.

**State the fixture cannot vary** (Revs):

- Values a shim reseeds on every call are invariants of every case. Code conditioned on them
  is unreachable from the harness, so test it through determinism or the picture instead.
- Platform-layer state is pre-state too: an emulated OS cursor, an unwind flag, a relocated
  global. Reset it per case.
- One global PRNG shifts every later fixture's coverage when a fixture is added. Reseed per
  fixture, and never call a reseeding helper in a loop condition.
- A fixture whose oracle and twin read different representations stages both from one value.
  For example, write a distance and the original's float of it, using the real tables.

## 5. Results, not implementation details

"Faithful behaviour from the user's point of view, not exact replication of the original
architecture" (user decision, Revs). The differential pins results the rest of the program
and the player can observe, not the transliteration's working notes.

**Implementation details, and ignorable:**

- scratch cells nothing outside the routine reads;
- registers and flags dead at exit;
- the order or count of writes to a cell whose final value matches.

**Results, and exact:** every cell any other code reads. A written reader audit decides
this, and it must include:

- the transliterated code, through hooks and re-entry on every variant (circuit, level,
  mode);
- the next pass, because one producer's scratch is the consumer's input;
- attribution on the authentic engine under the reference emulator, which reaches arms the
  port's scenarios don't.

**Using the ignore list:**

- Use it only for proven-dead cells, scoped to the one fixture, with the proof next to the
  entry. Adding an address to make a test pass launders a faithfulness bug into a green run.
- A whole-RAM determinism check has no ignore list. A dropped scratch write is re-recorded
  there with the reader audit quoted in the commit.

**Tolerances.** An accepted numerical departure (Revs: one `DIVU` instead of the original's
truncated-divisor quotient, ±1 LSB) uses a tolerance hook, not an ignore mask.

- Check in the space where the error model is exact: the twin exact to the true quotient,
  the oracle within its derived slack. A ±N band on an output is not that check.
- Derive the bound, and tighten it where the arithmetic allows.
- The tolerance must fire, print its census, and be sabotaged at bound + 1.
- The picture gate confirms that the departure is the one the user accepted. Classify every
  new differing pixel.

## 6. Sabotage every gate

**A first-run PASS is indistinguishable from blindness.** Inject a few deliberate defects
into every new gate, oracle, fixture and tolerance. Confirm that each fails, then remove
them (Revs, Rescue on Fractalus).

**A sabotage must be reachable in value space.** Moving a threshold to a value the program
cannot produce proves nothing. Check parity, masks, floors and BCD constraints (Revs: `>= $28`
became `>= $27` on an always-even value).

**When a sabotage survives,** the explanations are:

- the fixture never reached the code: probe what the pre-state actually became;
- the effect is provably unobservable: prove it by reading the callee, and record the proof
  at the code;
- the output heals itself: later writes overwrite the disagreement, so steer the pre-state
  into the real table ranges and run more cases;
- the oracle shares the input the defect lives in: see §7.

**A sabotage run can lie** (Revs):

- **Stale binary.** Unrelated defects report identical small mismatch counts. Remove the
  object and binary before every sabotage build.
- **Saturation.** A count equal to the total case count is every case failing, which is
  honest. Tell it apart from staleness by the first differing byte.
- **Concurrent edits.** A sabotage script that restores the source clobbers edits made while
  it ran.

**A control the gate erases is not a control.** Ask where in time and space the defect is
observable, and compare that with where the gate samples (Revs):

- an end-of-run dump misses a one-time prologue effect or a mid-run transient;
- a screen dump misses a cell the frame repaints;
- a picture gate over some lines says nothing about the others.

Change an input rather than a result, and verify the control per gate. Read the gated count,
not the printed listing. Compare summary counts before per-line listings, and never diff two
runs captured with different amounts of output.

## 7. What a differential cannot see

- **A differential is blind to what its two sides share,** in code or in input.
  - A re-decode check that calls the same expansion leaf cannot see a bug in that leaf.
  - A classification derived from an input both sides read is wrong identically on both
    sides.

  Name the shared thing, state the oracle's scope at the oracle, and gate that thing another
  way: by argument, by the picture, or by a path that doesn't consult it (Revs).
- **A pass is a pass over its window.** Run a new oracle for at least twice the window that
  first reached every arm it guards. Bisect only with the trajectory pinned (Revs: a
  2500-field PASS failed over 5000 fields).
- **Oracles over the same rows share their scope exclusions,** with the reason stated at
  each one.
- **A derived table needs a staleness guard,** not just a regeneration command. Regenerate
  it and fail on any difference.
- **Never compare memory or pictures between builds of different speed** at a fixed field
  count. The simulation has advanced to a different place. Use an in-process oracle.
- **A guard that works may be the bug.** When a check behaves as designed but the behaviour is
  still wrong, test whether the check itself suppresses the corrective action. It is the same
  family as caching a write-only register ([Amiga hardware](amiga-hardware.md#write-only-registers)).

## 8. Whole-program determinism

- **Keep runs deterministic:** a fixed-seed PRNG, no wall clock, no `rand()`. Anything the
  harness emulates must behave identically for twin and oracle, or the differential compares
  two machines.
- **Drive the real engine for N frames with the clock pinned,** dump all guest RAM, and
  require byte equality with a recorded reference. This is the gate for changes that alter
  the oracle as well as the twin: the generator, the CPU model, the memory representation.
  It is also the gate for drivers that can have no fixture (Revs).
- **Record several trajectories, because one trajectory is not a workload.** Revs records
  parked, driving, steering, each session kind and a crash. A missing engine-sound step was
  identical when parked and failed when driving.
- **Check that the gate can fail:** an unpinned clock diverges, and two configurations never
  compare equal. A wrong flag rule can hang the run instead of diverging, so a run that never
  reaches its dump is a failure.
- **Record only from a clean tree, after the change is proven correct.** Re-record, clean,
  and check again: a sound reference survives a clean rebuild. A record taken after a
  differently flagged build fails consistently, with the same byte count from any build, and
  reads like a real regression (Revs).
- **Never re-record to make a failure pass.** Record baselines before changing the generator
  or CPU model, and compare all affected trajectories afterwards.

## 9. Behaviour against the reference

**Milestones and replays**

- **Compare named milestones and comparable outputs:**
  - guest state, video state, sound and device events;
  - files and control-flow landmarks.

  Every negative observation needs a positive control proving execution reached the
  surrounding path (Slicks).
- **Replays:** use fixed ticks, controlled RNG seeds, recorded input edges and compact state
  digests. Compare persistent state and important events, not only screenshots (Downwell).
  Compare digests at identical ticks. Both CPUs must use the same precision policy (Downwell:
  table against portable atan).
- **Different CPU speeds need not show identical intermediate frames.** Capture state pairs
  (Vette).

**Lockstep against the reference** (Revs)

Replay the port's run on the reference, frame for frame:

- Log every input poll with the question asked and the answer given.
- Log every read of an entropy source, such as a cycle-timed VIA timer. The reference
  answers each poll from the log, and the replay stops at the first poll that asks a
  different question, because that means control flow diverged.
- A diff tool names the first frame where the state differs.

Making two machines agree took several fixes, each one found as a measured divergence first:

- force lottery values, such as the starter's random catch;
- replay the entropy reads;
- align defaults the two front ends set differently (Revs: the wing angle, which feeds grip);
- build with the original's exact arithmetic, because the physics read the picture and a
  one-pixel edge shift became a different trajectory.

State each excluded region at the comparison tool, with the reason:

- scratch cells the port doesn't reproduce;
- OS workspace;
- interrupt-rate counters;
- stale slots past live cursors.

**Driving the game for coverage**

- **An autopilot that reads only the game's own state** and presses the player's keys changes
  no engine code and stays deterministic. It reaches corners, crests and whole laps that
  straight-line trajectories never see (Revs).
- **Gameplay regression suites:** each case requires its own success record, rejects loud
  stops, and cannot pass by timing out. A fixture that places state at a decoded checkpoint
  proves that path, not uninterrupted play (Vette, Alone in the Dark).
- **A demo is a performance workload, not proof of playable controls.** Ferrari Formula
  One's demo and state oracles passed while ordinary throttle from rest failed. Exercise
  real press/hold/release combinations through the emulator's native input path and verify
  resulting player state: launch, braking, coasting, steering, manual gears and restart.
  Do not substitute direct writes to game control variables. Log actions and release held
  inputs on cleanup. Shared debugger input consolidation is tracked in
  [open work](../open-work.md#shared-debugger-keyboard-and-mouse-input); the project-local
  commands are not capabilities of every installed emulator.
- **An early checkpoint is evidence only for that endpoint** (Alone in the Dark).

## 10. On-target checks

The host harness cannot see Amiga-only code, endianness or beam timing.

- **Keep a WHDLoad diagnostic entry within the positive signed-word range.**
  `ws_GameLoader` is relative to the slave header, not to an appended payload.
  Assert `0 <= entry_offset < 0x8000` before writing it; an unsigned 16-bit pack
  accepting a larger value does not prove a valid boot entry. Growing VERIFY
  code can cross this limit while the lean build still boots. Use a nearby
  trampoline to the distant selection wrapper, preserve its entry ABI, and
  range-check the trampoline's own branch or address calculation. Verify a real
  boot and a nonzero diagnostic count after the repair. A missing initialized
  marker is a failed capture, not an arithmetic mismatch or a capacity result
  (Ferrari Formula One).

- **Target-only assembly needs an in-process differential with a nonzero check count.** The
  assembly and its C oracle run back to back on identical state in every call, and are
  compared. Inline assembly is unverified until it has run on the target: a ROR/ROL-X bug
  assembled and disassembled correctly (Revs, Rescue on Fractalus). Keep the portable C or
  C++ version as the oracle (Downwell).
- **An oracle that reads ISR-written state can race.** Snapshot before the change, run the
  oracle on both sides, and discard calls where they disagree (Rescue on Fractalus).
- **Shadow execution for simulation changes** (Slicks):
  1. At each wrapped call, snapshot the state.
  2. Run the reference, restore the snapshot, and run the native routine.
  3. Compare block hashes. Record the first differing block and continue from the reference.
  4. Fail on a mismatch, an error or an unexercised site.
- **Retention check for drawing-order or dirty-region changes** (Slicks): run every update
  from a snapshot with retention off, then for real, and compare the surfaces and caches.
- **Verify C2P by decoding every pixel,** including those outside dirty areas. Never take FPS
  from that build (Alone in the Dark, Vette).
- **Prove a pure reordering on the host.** Compile the old and new bodies side by side over
  randomised inputs; 160 000 cases take seconds. It is the only check that reaches Amiga-only
  framework code. Then re-measure: byte-identical is not cost-identical (Revs).
- **Assert invariants the original hardware kept for free.** For example, check that the
  emulated stack pointer stays in its window, at both ends (Revs).

## Exercise the user's route as well as isolated fixtures

Direct-entry fixtures are useful for a bounded routine check, but they can bypass the
allocation history and initialization that expose a bug. Wing Commander's side-cockpit
images failed after the ordinary campaign route because earlier scenes fragmented native
memory pools; a fresh flight fixture did not reproduce the missing cockpit rows.

For a scene or rendering fix, retain one short acceptance route through the real menus,
briefing and mission entry. Include the reported user actions, such as Return to skip a
moving cinematic, view changes and the cache option used at the WHDLoad splash. Record
actual cache state when relevant. Inspect allocation failures and available contiguous
blocks, not just total free memory. Do not silently substitute forced scene entry for this
route; describe what each fixture bypasses.

Pair the normal route with the focused native check rather than expanding every issue into
a machine matrix. Verify persistent overlays over several frames, transitions at a nonzero
prediction fraction and re-entry where history is retained. Native CPU checks establish
routine behavior within their modeled boundary; they do not establish complete gameplay,
visual acceptance or hardware performance.

## 11. Pictures

- **Judge appearance only from a clean real run.** The remote debugger greys the display, so
  a debugged run proves cost and state, never appearance (Revs).
- **Decode screenshots against memory dumps** rather than eyeballing them. Fixed store
  addresses map to screen positions: crop that region from a reference frame and look
  (Revs).
- **A dump of the published buffer is memory, not the beam.** DMA-level faults show only in
  per-field screenshots from an instruction trace (Downwell).
- **Picture gates compare a window.** A gate that prints a difference and still passes is a
  pass for the gated lines only.

## 12. The faithfulness seam and deviations

**Decide the seam rule before the first native routine.** The question is whether the
original code still defines the routine's observable behaviour.

- If it does, the routine stays in the validated tier. Its platform variation is a small
  guarded addition: publishing a dirty region, or skipping a hardware tail the copper already
  handled.
- Moving a routine out of the validated tier costs its proof for good. Prefer the smaller
  `#ifdef` (Revs, Rescue on Fractalus).
- A subsystem behind an OS call is OS behaviour. It is faithful, shared and validated against
  real hardware, while its Amiga half only reproduces the chip state.

**Fidelity before improvement** (Slicks, Vette, Pokeri):

- Every deviation is either fixed or listed with its reason and the user's decision.
- Remove port-only additions, and don't add optional UI to hide a failure.
- Keep the original decisions and implement their services. Unknown calls stay named, loud
  stops.

**Undefined or garbage behaviour in the original is a user decision,** recorded as a
deviation (Slicks).

**Timing departures are written departures** (Revs, Slicks), for example a
frame-rate-independent simulation or a real-time clock. Each has a per-piece argument and its
own gate; see [fixed-time simulation](../playbooks/fixed-time-simulation.md).

**Before calling drift a bug, look for the original's own compensation table.** A table that
equals the formula the hardware model implies proves both the model and the faithfulness from
the binary alone (Rescue on Fractalus).

## 13. Coverage

- **Enumerate modes, difficulty levels and session types,** and ask which code each one
  excludes. A mode the tests never run is a whole untested subsystem. Practice skipped the
  multi-car path, and the first race hung (Revs). A one-line grep for the gating flag finds
  the exclusion.
- **A body no scenario drives is unproven, not dead.** Static analysis gives an upper bound,
  a trace a lower bound (Slicks, Revs).
- **Delete oracle-tested code the shipped game never links,** together with its tests
  (Slicks: 2035 lines).
- **Read bounds from the instruction, never from the first example.** Assert the instruction
  shape you rely on (Revs: a patch count differed per track).
- **A static count of a dynamic mechanism under-counts by exactly its dynamism.** The
  operand encoding is the strongest evidence of the legal target set (Revs).
- **Untranslatable input fails at generation or reports loudly at run time.** A silent no-op
  looks exactly like working code, and a `TODO` in generated output is not loud (Revs,
  Slicks).
