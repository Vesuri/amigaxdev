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
