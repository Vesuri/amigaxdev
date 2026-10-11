# Fixed-time simulation in a WHDLoad patch

Use this after identifying the game's time sources and getting the user's decision on
simulation cadence. These checks complement the [new-game playbook](new-game-playbook.md#9-understand-game-time-before-optimising-anything).
Legends of Valour `docs/simulation-timing.md`, `docs/one-degree-turning.md` and
`tools/turning_input_validate.sh` provide concrete implementations; Stunt Car Racer shows
what changes when the physics rate itself is raised. Their constants and patch offsets are
game-specific. Uncapping drawing and smaller timesteps are in
[simulation and presentation](simulation-and-presentation.md).

## Separate completed ticks from elapsed-time observations

A single-task game cannot update its world while it is drawing. A fixed-step accumulator
can account for elapsed fields and run overdue ticks after drawing, but it does not make
state at every VBL identical across rendering rates. A VBL snapshot can interrupt either
an expensive draw or a partially completed simulation update.

Use both comparisons:

- **Matched completed ticks:** break at the common tick-completion point and compare the
  decoded world, actors, player, animation, clocks and input. Use identical initial state
  and input history. Deliberately delay drawing in VERIFY to expose frame-dependent work.
- **Equal elapsed fields:** sample a fixed VBL interval and record completed ticks, pending
  fields, consumed fields, pause state and any recovery counters. Account for different
  initial clock epochs. This checks elapsed-time accounting and bounds update latency.

A completed-tick match alone does not prove that the right amount of time was consumed.
Conversely, different world snapshots at the same VBL do not alone prove a bad time step.
Report the pending-time bound and any skipped/rebased time; do not call catch-up zero-latency.
Use state observations for game speed and fixed-window traces for rendering cost.

## Preserve the input that belonged to each tick

Sampling the current mouse or key state repeatedly while catching up applies today's input
to older ticks. Record input against the clock consumed by the simulation instead:

- Keep pointer/button history and relative hardware-counter deltas distinct. Test signed
  deltas, counter wrap and heading wrap in both directions.
- Enter direct mouse control through the native UI before testing it. An arrow-button
  route with injected relative motion may never exercise mouse-look at all. Inspect mode
  state at the anchor, then compare consumed input with the resulting headings.
- Exercise repeated switches between pointer and relative modes. Discard/rebase deltas at
  the same native boundaries as the game so motion does not leak into the next mode.
- For console-driven keyboard input, preserve native decoding, repeats, blocking reads,
  menus and text editing. Test queue pressure, producer backpressure and shutdown as well
  as ordinary movement keys. Do not let a collector outlive the game or consume modal
  input on the wrong path.
- Input history is finite. Define and instrument overflow behavior; test ordinary play
  and long pauses so a test-only history limit does not become a release abort. If the
  policy discards elapsed input/time, expose that as recovery, not a successful exact match.

## Audit every kind of game time

Player movement looking correct does not establish that animation, AI or combat is correct.
Find the writers and consumers separately: movement compensation, actor updates, animation
phase, texture animation, cooldowns, daily events, projectiles and visual randomness.

Retain native modal boundaries. Menus, save/load, text messages and scripted time jumps
must not accumulate a backlog of world updates unless that is the intended game behavior.
A useful design keeps the native clock running for UI deadlines, counts active world fields
separately, and gives world logic the logical time of the tick being processed. Never apply
that design blindly to all clock readers; some intentionally need live time or native jumps.

Combat may have a different cadence from ordinary world updates. Preserve that separately
and test entry, exit and resumed world time. Run native pause/save/load and real console
editing routes; a synthetic state toggle does not prove the real boundary is handled.

Measure logic-only catch-up ticks separately from ticks that also draw. A faster-looking
renderer can still lose frame rate when a slow machine must do more world updates. Keep
rendering caps and beam synchronization separate from the simulation decision.

## Raising the update rate: decide per quantity what scales

Stunt Car Racer runs its physics six times as often as the original (about 8.3 Hz to 50 Hz,
with several physics iterations per displayed frame when drawing is slow). The lessons are
in its `AGENTS.md` §Frame Rate Conversion; the per-operation conversions are in
[simulation and presentation](simulation-and-presentation.md#analyze-a-smaller-timestep-by-units-and-writers).

- **Read what a "velocity" really is before scaling its thresholds.** Stunt Car Racer's
  suspension "velocity" is `delta × momentum / 256 + position`, so the position term
  dominates hard landings: the same landing reads `$1968` at 10 FPS and `$1A50` at 60 FPS
  (1.05×). Damage and impact thresholds on it need no scaling; scaling them would have been
  the bug. Collision forces and distances are magnitudes, not rates, and stay too.
- **Scale what integrates over the step,** and only that: forces and accelerations that are
  added once per tick (momentum amplification and pitch/roll rates, ×6 in Stunt Car Racer).
- **Keep spring-to-damping ratios, not individual constants.** A stiffness scaled with the
  rate makes the body that much stiffer. Stunt Car Racer kept its spring at ×2 and made
  ground damping about 6× stronger per iteration.
- **Damping scaled for the rate is only right where a restoring force compensates.** Airborne,
  with no spring, the scaled damping removed angular momentum about 36× faster per real
  second and dipped the nose past level after every ramp; the airborne branch keeps the
  original `÷16`. Split damping by the state that decides whether the force exists.
- **Classify every timer by where it runs:**

  | Timer runs | Scale |
  |---|---|
  | at display rate, outside the physics loop | the initial value, and decrement by the elapsed fields |
  | inside the physics loop, every iteration | the initial value only |
  | inside the physics loop behind a fixed-rate pulse (an accumulator that overflows at a constant wall-clock rate) | nothing |

- **Over-sampling is not mis-scaling.** An accumulation that fires per physics iteration fires
  six times as often during the same bounce. Stunt Car Racer divides that accumulation
  (by 8, close to 6) rather than changing the constants it compares with.
- **Test the behaviour, not the arithmetic.** What the maths says should scale can differ from
  what the code's structure does; judge ramps, landings and bounces in play.

## Precision and control feel are separate decisions

Finer rendering angles need not mean smaller UI-button steps. In Legends of Valour,
one-degree mouse precision was accepted while the button tap/repeat override was removed.
When changing precision, test direct mouse motion and UI commands independently. Retain
the native command handler when its behavior is wanted; verify its relocated target in
captured memory rather than merely checking that a new wrapper returns plausible steps.

If precision requires larger lookup tables, generate them from mathematics and the local
original at runtime. Preserve original rows at legacy angles, compare generated rows with
an independent model, and test full-angle rendering and all view sizes. Publish the table
pointer, stride and angle units together only after allocation/generation succeeds. On
failure keep the original pointer and units together; never index a coarse table using a
finer angle unit. The game's original table and the patch's allocation need distinct owners.
