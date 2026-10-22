# Fixed-time simulation in a WHDLoad patch

Use this after identifying the game's time sources and getting the user's decision on
simulation cadence. These checks complement the [new-game playbook](new-game-playbook.md#9-understand-game-time-before-optimising-anything).
Legends of Valour `docs/simulation-timing.md`, `docs/one-degree-turning.md` and
`tools/turning_input_validate.sh` provide concrete implementations; Stunt Car Racer shows
what changes when the physics rate itself is raised; Red Baron prices a fixed step before
building it and Their Finest Hour smooths a per-frame step. Their constants and patch offsets are
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
- Distinguish auto-repeat from a burst of fresh presses across slow screen transitions.
  Rejecting repeat-qualified events does not remove fresh Enter/Space presses queued
  during a fade. When a transition is deliberately non-interactive, discard its pending
  input at the boundary where the next screen becomes ready, then verify fresh input
  still works. Also check mixed keyboard/joystick readers: a queued key must not bypass
  hardware polling and then select from stale cached joystick state without consuming
  the key. Grand Prix Circuit exhibited both mechanisms; test them separately.
- Input history is finite. Define and instrument overflow behavior; test ordinary play
  and long pauses so a test-only history limit does not become a release abort. If the
  policy discards elapsed input/time, expose that as recovery, not a successful exact match.

For speed acceptance, compare after equal durations of **applied input**, separately from
input-to-update and input-to-display latency. Road Rash's original variable-step path could
apply a newly sampled throttle state retroactively across the preceding frame. Correcting
that behavior changed distance at a fixed wall-clock checkpoint even when equal applied-input
durations produced matching speed. Record when each input was sampled and which simulation
time consumed it. Retain equal-elapsed-field checks and latency bounds as separate gates;
matching applied-input duration must not hide delayed input, dropped time or catch-up backlog.

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

## Price the catch-up before choosing the quantum

A fixed step that the slowest target cannot sustain turns into a growing backlog. Before
implementing one, project its cost: measure one world tick's cycles (routine cost with
callees) and the rest of a frame's work, then work out ticks per second, world-only
utilization and the render rate that is left for every speed setting. Red Baron
(`docs/game-time.md`) did this for 225-unit world ticks on the A500:

| Time Scale | World ticks/s | World-only utilization | Render fps left |
|---|---:|---:|---:|
| 0 | 3.4 | 20% | 1.5 |
| 40 (default) | 8.2 | 48% | 1.0 |
| 60 | 26.9 | 159% | unsustainable |

A 100-unit quantum alone came to about 109% at the default setting, which ruled it out.
Make the projection an explicit acceptance gate rather than a claim: the plan names what
it does not yet prove (convergence, sustained catch-up of code that does not exist yet)
and what changes if the gate fails (a coarser quantum, or optimising first). Where a
setting is beyond the machine, keep the debt, skip rendering while behind, service input and
audio between bounded batches of ticks, and report the supported CPU and speed envelope.
Do not claim that catch-up always holds nominal speed.

## A variable step measured per frame: average it when intervals count frames

Some games keep a variable step and set countdowns as multiples of it, counted down once per
frame. Their Finest Hour's T (frames per second, from a boot benchmark) scales both the
per-step motion and its countdowns: a gun's reload is T/3 frames, a bullet lives 2T frames.
Its `docs/internals.md` "Real-time simulation" describes the replacement:

- Measure T every frame, but from an **average** frame length that moves 1/8 of the way
  to each frame's length. A countdown lasts its time only while T matches the frames that
  follow it. With T from the last frame alone, frames alternating between 2 and 3 fields
  gave T 25 and 17 by turns and gaps between shots of 12 or 20 fields; with the average,
  14–18 (mean 16.1 against 16.7 nominal).
- Carry the time owed (frame lengths less the steps taken) and add part of it (a quarter) to
  the next step, so game speed stays exact over time. Clamp T to the range the game handles
  and let a very long frame (a pause or a disk load) add no time.
- Scale inputs that grow with the frame's length (mouse counts divided by T) so control
  response does not depend on the frame rate; pick the scale that matches the original at
  its usual rate.
- Measure the field rate rather than assuming PAL, and leave the boot benchmark alone if its
  value is used outside the replaced loop.
- At large T, per-step increments become small, and the game's truncation of each one loses
  speed and turn rate. Carry the fractions per object in 16.16 (Their Finest Hour: 4 649 →
  4 712 units/s at 50 fps, against 4 715 nominal).

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


## Audit clocks beyond movement

A smoothed frame divisor can improve pacing, but it does not repair a countdown
initialized as `seconds × T` when T later changes. Give each timer an explicit
clock: simulation time, unaccelerated control time, display time or hardware
protocol timing. Preserve eligibility gates and whether an initial opportunity
is immediate. Carry elapsed-time overshoot when servicing repeated deadlines;
checking only once per rendered frame can lose events during slow frames.

Follow the world-call graph and every movement, impact and AI dispatch entry.
Trace writers of quantities before deciding they are rates: event damage,
resource deductions per successful shot and derived engine power do not get a
second timestep multiplier. A native fraction accumulator may already solve a
division; test it before replacing it. Conversely, a resource stored in fixed
point can still discard the remainder below its least significant bit. State
the size of that error instead of implying a large gameplay effect.

Separate tasks within the same interrupt. Audio sample queueing can require
every physical field while its volume envelope needs a fixed elapsed cadence.
Mouse counter deltas measure distance and must all be retained; joystick ramp
steps and keyboard repeat count time. Releasing or reversing a controller must
not erase movement that a slower consumer has yet to read. Test PAL/NTSC and
independent producer/consumer rates. Hardware handshakes and beam/blitter waits
are a different class from user-visible delays.

## Recording with a changing timestep

Recording one input tuple per update does not establish a fixed-duration movie.
Choose capacity in elapsed time, store each update's actual timestep (including
acceleration), and preserve RNG history where outside-world calls can advance it.
Playback rendering can consume zero or several complete recorded updates;
viewer camera commands and message visibility still need the current display
clock, rather than the most recently recorded divisor. Test the final tuple,
pause/resume, single-step and elapsed-time fast-forward separately.

Filter and normalize physical input before recording it. Replaying processed
input must not apply a dead zone again using the viewer's current mouse/joystick
state, nor substitute a live UI key for the recorded command. Native save tables
often omit state that became significant after patching. Maintain an explicit
manifest of private fractions, timers and generations; automatically reject new
mutable fields missing from it. Keep movie-start and suspended-live snapshots
separate, and keep host calibration/preferences out of restored simulation state.

Version the extended movie layout, bound every count and validate truncation.
An old movie without timestep history cannot provide exact enhanced replay;
document the compatibility limit. Rewind correctness in a CPU fixture, native
file I/O, rendered UI behavior and a live-emulator mission are separate evidence.
Their Finest Hour's timing audit and recording checks demonstrate this split.
