# Simulation and presentation in a WHDLoad patch

Use this when uncapping drawing or assessing a smaller simulation timestep. It complements
[fixed-time simulation](fixed-time-simulation.md), which covers clock accounting, input
history and catch-up. These lessons come from Indianapolis 500 StingRay:
`tmp/dev/docs/game.md`, `tmp/dev/docs/slave.md`, `tmp/dev/docs/simulation-feasibility.md`
and `Games/Indianapolis500_Motion.s`. The equations and record layouts are game-specific;
trace their equivalents before transferring a patch.

## Snapshot what each view actually draws

A correct interpolation formula does not establish that its inputs are correct. Follow the
renderer backwards to its native inputs separately for driving, demo and replay. In I500,
the cockpit consumes car records, external demo views consume nodes a tick behind those
records, and instant replay updates only the nodes. Snapshotting the records in every mode
can pass a formula check while replay cars stay frozen.

Verify two independent properties: the saved snapshot equals the native input the renderer
would consume, and the rewritten pose equals the intended formula. Exercise native UI paths
into cockpit, demo, instant replay, pause and menus, including transitions between sources.
Keep renderer copies separate from authoritative simulation state. Reset snapshot history
at camera cuts, teleports and source changes; define what happens when simulation stops.

Removing a main-loop wait also accelerates anything that advances once per loop pass.
I500's replay wipe needs the original wait even when ordinary drawing is uncapped. Audit
transitions and animation state machines, and compare durations using the same emulated
clock, not frame counts. Smooth racing alone does not validate the main-loop change.

## Predict from the native update order when possible

With alpha in [0, 1] measuring time since the latest completed tick:

- Interpolation displays `previous + (current - previous) * alpha`, one tick behind.
- Last-difference extrapolation displays `current + (current - previous) * alpha`;
  it can overshoot when movement changes.
- If the next native pose is derivable, display `current + (next - current) * alpha`.
  This avoids using the previous tick's rate to predict a changed rate.

I500's opponents move using stored rates before their controllers choose new rates. At tick
completion those new rates therefore describe the next free-motion update. Derive `next`
with the native arithmetic: preserve the fractional track byte, wrap, signed word behavior,
and the order of lateral velocity and position updates. Use the shortest angular arc for
presentation. Predicting the endpoint does not prove the intermediate path is physical.

Compare each prediction with the next actual simulation pose. Contacts, resets and other
intervening writers can invalidate it; provide a correction/fallback policy. A match in
ordinary free motion is not a guarantee across collisions. Do not reuse the opponent model
for the player merely because the records share a layout: I500's player fields include
published displacement, and its next pose depends on unread input and different physics.

Extrapolation removes interpolation's deliberate presentation delay; it does not increase
input sampling or simulation frequency. Describe those limits separately from frame rate.

## Control memory layout in state comparisons

A bigger slave can change where WHDLoad loads the game. In I500 the option-disabled build
and the original demo diverged; an original slave padded to the same size reproduced the
same divergence from the unpadded original. At the matched load address, the padded original
and disabled patch matched the compared simulation state. This isolated a layout effect;
it did not prove why the original game depends on its address.

Record actual hunk bases and allocation sizes in local capture metadata, while keeping
published code references as hunk offsets. Compare original, layout-matched original and
option-disabled patch before attributing a divergence to new logic. Keep diagnostic
padding local and verify that it preserves executable contents and produces the intended
allocation layout. Align samples by completed simulation tick, with identical inputs.

A layout-controlled match does not establish equivalence to the normally loaded original,
nor does an option-disabled match validate enabled patches. State the comparison's scope,
classify renderer workspace separately, and retain the ordinary original comparison as a
separate acceptance question. Do not label unexplained differences as random noise.

## Analyze a smaller timestep by units and writers

Begin with static code analysis when that is the requested scope. Build an inventory of
state, units, all writers, consumers, update order and cadence before proposing experiments.
For a fine step of h original ticks, keep physical state units unchanged where possible:

| Operation | Conversion to examine |
|---|---|
| Integrating velocity or acceleration | Multiply the increment by h. |
| An explicit acceleration-times-step-squared displacement | Multiply that term by h squared. |
| Force depending on speed squared | Keep the force law; scale the subsequent integration. |
| Derivative from adjacent samples | Divide the difference by the new interval. |
| Exponential retention r per old tick | Use r to the power h for a constant target; quartering the gain is only an approximation. |
| Slew limit per tick | Scale the rate limit, preserving precision and saturation. |
| Collision response | Separate impulses, position projection, continuous forces and event-triggered damage. |

Check the original finite-difference horizon and filters before changing them. Keeping an
old-duration history preserves that window, not the meaning of an instantaneous derivative.
Mixed-use fields need separation: a displacement used to copy a pose cannot also become a
normalized velocity without auditing both consumers.

Integer precision can dominate the conversion. Quartering a word-sized increment can erase
small forces and widen filter dead bands. Use remainders or wider shadow state as needed;
all native writers, including collision, reset, pit and initialization paths, must keep it
consistent. Preserve signed rounding and carry semantics rather than assuming shifts are
interchangeable with division.

Smaller steps also change the integrator's response. With constant acceleration increment A,
semi-implicit Euler gives old-tick displacement `v0 + A`; four quarter steps give
`v0 + 5*A/8`, despite the same final velocity. Decide whether acceptance means a more finely
integrated physical model or preserving the original handling. A correction derived for
constant force is not automatically valid for collisions or nonlinear forces.

Audit AI, randomness, thermal updates, clocks, effects and replay recording independently;
calling them four times as often changes behavior even with correct player equations.
Four substeps in one old-tick burst do not provide evenly spaced input response. Establish
when input is sampled, how pending time is represented, and which consumers need each
intermediate state. Finally, simulation and display clocks can differ: roughly 60 Hz updates
shown at 50 Hz alternate step counts unless presentation compensates. Choose cadence and
presentation together, then define handling and timing acceptance before implementation.

## Interrupt-driven simulation needs a short protected snapshot

Do not assume simulation advances in the drawing loop. Grand Prix Circuit updates physics
from the VBL interrupt while foreground code draws. Removing a drawing wait therefore does
not itself change its simulation rate. Inventory the interrupt counters, input sampling,
physics period and independent game clocks before changing cadence.

If a foreground renderer copies several related fields, an interrupt can split that copy
between two physics ticks. Use a balanced OS Disable/Enable pair around the smallest complete
snapshot, preserving registers and native call/return semantics. Perform projection-table
rebuilds and other long work after Enable. Save all view inputs that must agree: road,
horizon, scenery and opponents can read different copies of the same pose. A consistent road
alone does not prove a consistent frame.

Validate both the copied values and the interrupt exclusion. Inspect executed PCs between
Disable and Enable, not just the VBR or a sampled counter, and retain a negative control.
Keep rate conversion separate from clock policy: finer physics need fractional remainders,
while lap clocks, decisions, damage and event gates may retain their original periods.

## LoadView is a publication request, not buffer retirement

A LoadView call can schedule a copper-list change without immediately stopping DMA from the
old screen. A call counter is therefore a publication marker, not proof that a bitmap is safe
to overwrite. Trace DMA bitplane pointers and CPU/blitter destinations through the handoff.
Grand Prix Circuit initially overwrote the displayed bitmap despite apparently alternating
its two software buffers; horizon flicker was a visible symptom.

Where the native main loop permits it, publish the new view and do CPU-only geometry work
while waiting for the next field. Before the first screen write, confirm the field has
advanced and drain the pending handoff. Other swap callers, pause and race-exit paths need
their own completion policy. Compare publication counts with completed displayed-buffer
changes and audit every pixel writer; do not report the former as visible FPS.

Derived projection tables also need lifecycle handling. Preserve canonical tables, derive
fractional tables from that copy, and restore the canonical values before the native next-race
initializer rebuilds dependent maps. Test a second race after a nonzero fraction. A first-race
pass can conceal cumulative table drift. Keep native duplicate-row selection rules intact
and require exact fetched-plane equality when the added fractions are zero.

## Redraw animation scripts without advancing them

Wing Commander's cinematic actors combine drawing with script-cursor advancement. Calling
such a routine on every displayed frame accelerates the animation; disabling its active flag
can select a different interpretation of the record and cause flicker. Audit the routine's
writes before treating it as a renderer.

For a bounded replay, retain the pre-tick script state and the committed post-tick state.
Stage the pre-tick fields needed to reproduce the current pose, draw, then restore the
committed fields. Include counters, random state and effect creation where the replay touches
them. Preserve background restoration and compositing order: moving actors, room labels and
window scenery must be composed on every newly drawn image even when their logical state
has not changed. Input polling is not a sufficient gate for drawing a persistent label.

Keep world simulation, bitmap script advancement, input polling and display publication as
separate timing owners. Wing Commander uses a 10 Hz world clock and, for selected bitmap
sequences, one animation update every three display fields (50/3 Hz PAL, 20 Hz NTSC).
Those are game-specific choices, not a general historical rate. Smooth transforms may still
advance on every render between bitmap updates. Check native per-cel holds as well as the
outer loop; one script update need not select a new bitmap.

At scene exit, restore temporarily borrowed authoritative poses or tables before clearing
prediction validity. Reset camera, object and effect histories at their actual ownership
boundaries, including skipped cinematics; a stale angular rate can move stars in a later
scene that does not natively rotate them. Do not erase native controls still owned by the
next mode, and do not confuse prediction reset with draining a pending display handoff.
Validate an early skip during motion and a second entry, not just a completed first pass.

## Give newly spawned projectiles an explicit presentation interval

A reused object slot is not proof of a continuous trajectory. Certify new identity at the
native constructor, invalidate the previous occupant's history, and determine whether the
first published position is the muzzle position or already includes a native movement step.
Predicting forward from an already advanced position can omit the visible near-muzzle
segment; waiting for two samples can instead hold the projectile still. Derive the first
interval from the native spawn/update order and velocity rather than borrowing ship history.
Apply the policy to every relevant constructor, not only the player's firing path.

Prediction is not collision detection. Bound visible prediction at a known impact or scripted
endpoint so that shots do not travel through a target before its explosion. Keep damage,
object retirement and collision tests on committed state; never pass temporarily staged
render positions into them. For fields such as asteroids and mines, verify which coordinate
space and object collection the native collision path actually reads. A convincing shot
image alone does not establish a hit on the same object.

Useful focused checks cover the first visible shot, the next native update, slot reuse,
an impact and scene exit, with prediction disabled as a control. Compare both authoritative
state and rendered positions. Wing Commander's spawn, intro-shot and field-contact fixes
illustrate these distinct failure modes; their offsets and record layouts belong in that
project's documentation rather than a shared patch.
