# Measurement method

How to get a number you can trust on the target, and how to decide with it. The rules come
from the port projects. Each rule names the project where it was learned and, where they
help, its measured figures. Related docs:

- [m68k optimisation](m68k-optimisation.md): what code costs.
- [Amiga hardware](amiga-hardware.md): what the machine costs.
- [headless FS-UAE](headless-fsuae.md): how to drive the emulator and gdb.
- [validation harness](validation-harness.md): whether a change is still faithful.
- [port toolchain](port-toolchain.md): build flags and link audits.

1. [Order of work](#1-order-of-work)
2. [Units: what to quote](#2-units-what-to-quote)
3. [Instruments](#3-instruments)
4. [Verify the instrument](#4-verify-the-instrument)
5. [A/B discipline and baseline trajectories](#5-ab-discipline-and-baseline-trajectories)
6. [Pricing a change](#6-pricing-a-change)
7. [The experiment loop](#7-the-experiment-loop)
8. [Budgets](#8-budgets)
9. [When to stop](#9-when-to-stop)
10. [Reporting](#10-reporting)

## 1. Order of work

1. **Measure the original first.** Run it under its reference emulator and record its own
   frame time, with a calibration line printed beside the figure. For example, one PAL field
   should measure 40 000 cycles against the expected 39 936. Every port figure is quoted
   against that. (Revs: the real BBC needs 97.0 ms per frame, median over 165 settled frames.)
2. **Get an end-to-end skeleton running on the target, then profile it.** Do not choose
   optimisation work or promise a frame rate before that. (Rescue on Fractalus: the
   "algorithmic floor" turned out to be GCC's floor. Slicks.)
3. **The user sets the bar.** That covers the frame rate and which workload must meet it:
   best case, combat load, mean, p95 or maximum. Calling something impossible needs a
   hand-written assembly datapoint. (Rescue on Fractalus: the bar was 25 FPS on the best
   case, and combat could sit lower.)
4. **Measure, don't theorise.** The headless emulator and gdb loop finds timing and render
   bugs where static reasoning keeps failing. Keep it cheap enough that measuring beats
   arguing.
5. **Re-measure; never quote an old number.** A figure belongs to one build, probe set,
   window and workload. (Revs: a stale "~6 FPS", really 14.4, steered scope for months.)

## 2. Units: what to quote

| Rule | Why |
|---|---|
| Quote ms per frame, or raster lines (64 µs; a PAL frame is 312/313 lines, 20 ms) | A percentage of an unknown total is not a measurement |
| Displayed FPS is quantised to `50/N`; size changes in ms | The frame wait pads work up to the next field. In Revs, the pad absorbed 75% of an added 7.9 ms, and a 12.5 ms saving read as +1.5% FPS (under-read about 4×) |
| Report work and cadence separately; give mean, p50/p95/p99, maximum and the count over budget | The phase table of the last frame is not the frame with the most work (Slicks) |
| Time in emulated fields or beam ticks, never host wall time | Warp and host load change nothing emulated. A 30 s wall window covered 75 s of emulated time in one run and 144 s in another (Revs) |
| An absolute figure belongs to (build × window × workload) | Rescue on Fractalus: one binary read 24.88 FPS over fields 1900–4900 and 23.57 over 4900–7900 |
| Don't add gains measured in different scenes or transfer them across CPU presets | Vette |
| Time saving is `1 − new/old`; FPS gain is `old/new − 1`; say which | Vette |
| Cycles in a trace are emulated CPU clocks (142 102 per PAL field for a 68000) | Downwell |

## 3. Instruments

Pick the instrument by the question. Shares, progress, exact attribution and correctness
each need a different one.

| Instrument | Answers | Limits |
|---|---|---|
| Frame counter that the program samples: `FPS = 50 × frames / vbi`, with gdb reading the counters only at the end | The standing baseline | Quantised to `50/N`. Under-reads a win the frame pad absorbs; over-reads a cross-run win when the workload has shifted |
| Whole-update work timer in the normal build: raster stamps around step, HUD, audio and C2P, excluding the sync wait | Progress, the work distribution, frames over budget | Needs a deterministic fixed-clock benchmark; it must refuse a stale executable and print a final-state hash (Slicks) |
| Phase brackets (beam stamps) with an emulated-field window | Shares within one run; a field-bounded A/B resolves 0.03 ms on a 197 ms frame (Revs) | Brackets cost real time; include nested callees; bill an ISR to the phase it preempts |
| CIA-B timer PC sampler with a jittered period, recording PC and SR from the exception frame | Shares by routine, about 12% uniform overhead (Slicks) | Shares only. **Never sample through gdb interrupts:** FS-UAE services them only at vsync. That doubled C2P's share and hid physics (Slicks), and filed an autovector stub as "Kickstart 8%" (Rescue on Fractalus) |
| VBL-counted phase marker: scopes publish a phase word, and the VBL handler counts it once per field | Statistical attribution without per-scope clock reads (Downwell) | Aliases with repeated work; a short phase can get no samples |
| FS-UAE instruction profile (Barto format, `monitor profile`) | Exact cycles per PC over whole fields; call stacks can be rebuilt from `jsr`/`bsr` and SP, with interrupts kept on a separate stack (Downwell, Vette; shared as `amigaxdev.callprofile`, which also chains 100-field chunks) | Code must be in the first hunk. No breakpoints in the window. The first and last frames are partial. A blitter stall can carry its cycles into the next field. Moving code changes attribution |
| aprof FS-UAE, installed by AmigaXDev (`FSUAE_APROF`, `monitor aprof start/stop`) | Every instruction's cycle units, wait states included, per PC; timing for every CPU Chip-bus access; a call tree that includes Line-A traps (Alone in the Dark) | Cycle-exact 68020–68060 without an MMU model; refuses MMU and fast mode. PCs outside 24-bit space are kept only in the 16 MB Zorro III window at `0x40000000`. The emulator's memory model, not hardware proof; on 040/060 it is an instruction count (below) |
| In-process differential: new and reference code on identical state in one run | The cost ratio of a replacement, and correctness | Quote the ratio; absolutes swing 15% between runs while the ratio holds to 0.5% (Rescue on Fractalus). Below about 500 cycles per call the timing column can have the wrong sign |
| Shape probes: counters over a routine's own input distribution | Which cases dominate. Two special cases absorbed 47.7% of a rasteriser's subdivisions (Rescue on Fractalus) | One-off; remove them afterwards and keep the record |
| Host build as a census | Exact call and line counts, matching the target (Revs) | Never timing |
| Doubling or removal arms: run an idempotent pass twice, or delete it | The price of a sub-step without a bracket | Removal gives a ceiling only |
| Static objdump cycle count | Finds defects | Over-reads about 6× at a grain of 2–7 instructions (Revs). Use it to find a defect, never to size one |
| Read-only probes on the normal build | Acceptance figures | Ledger and trace observers add about 6–7%, and once inflated cold start by about 45% (Pokeri) |

**FS-UAE's 040/060 timing is an instruction count.** Its cycle-exact 040/060 loop charges no
time to instruction execution or to 32-bit Fast RAM accesses. Time advances only on
Chip/custom accesses and multiply/divide, plus one colour clock after every four
instructions that advanced nothing. The emulated CPU therefore runs about 14 million
instructions per second whatever frequency is configured: 040/25 and 060/50 came within 1 FPS
of each other (Red Baron). aprof books those charges as `gap`; it equals the zero-time
executions × CYCLE_UNIT/4. Price emulated 040/060 work by instruction count plus Chip time,
and confirm hardware frame rates on a real accelerator.

Instrument rules:

- **Build diagnostic flags off by default and never release them.** Clean when toggling.
  Audit the release for diagnostic markers (Slicks, Pokeri).
- **Never compare an instrumented total with a shipping total.** Take ratios from the
  instrumented build and absolutes from the plain one. A probe build ran about 35% slower in
  Rescue on Fractalus.
- **Put no gdb stop inside a measurement window.** A conditional breakpoint biased FPS by
  10× in either direction, and it agreed with the truth on one build while being wrong on
  another (Revs, Rescue on Fractalus).
- **Calibrate a new bracket with a known burn:** add N × a known cycle count and fit the
  slope. An empty bracket at the same call rate gives the probe floor (Revs).
- **Bracket each arm of a routine separately.** An average over calls that do different jobs
  hides the finding.
- **Accumulate beam brackets through a monotonic epoch**, not `beam − beam`. The raw
  difference drops brackets that straddle the frame wrap, and it drops the longest phases
  hardest (Revs).
- **A VBL handler timestamp is not necessarily the field boundary.** Interrupt masking can
  delay entry by several lines. Unwrap the physical beam independently, then reconcile it
  with the interrupt epoch. For NTSC, account for alternating long lines and the observed
  LOF/LOL bits rather than assuming every line or field has one fixed length (Stellar 7).
  In UAE's `vhpos_adj` convention, VHPOSR HP=0 denotes the final clock of the reported line;
  HP=1 denotes clock zero with the previous line's VP. Test these rollover cases and reject
  non-monotonic or inconsistent timestamps instead of clipping negative durations.
- **Calibrate debugger beam observations before using them without instruction traces.** Use
  the exact same binary and deterministic scene with an independent instruction trace on a
  supported CPU; compare presentation-field patterns, complete-call durations and matched
  state. Retain raw observations and quantify disagreement. Such scopes include interrupt
  execution and wrapper overhead; blitter-wait elapsed time is not pure DMA cost. Missing
  blitter DMA records in a non-cycle-exact recorder do not mean no blitter work. Keep the
  ordinary field/counter interval as the throughput measurement (Stellar 7).
- **Keep inclusive and exclusive measurements apart.** Never add a parent's inclusive time to
  its children's, or add independently selected probes together (Downwell, Slicks).
- **Label a capture that covers only part of a stall** as slice time, not frame time
  (Downwell).

## 4. Verify the instrument

A first reading proves nothing until the instrument has failed on purpose. The rules below
each replaced a habit that had already cost time.

**Accounting and controls**

- **Print a total-accounting check on every run**, for example "bracketed/elapsed must be
  about 100%" and "body ticks per field must be about 1". At 1.4 FPS, a profile that lost
  beam deltas at the frame wrap accounted for 4% of the frame and named the wrong hot path
  (Revs).
- **A hedge is not a control.** A note saying "this zero may be a wrapped bracket" under a
  headline table does not license the headline. Test the doubt or don't publish the table.
- **Suspect the instrument hardest when it agrees with your expectation.**
- **Every "not observed" needs a positive control in the same run**: a landmark proving the
  run reached the surrounding code. Three zero-hit probes on main-loop sites came from a run
  stuck in the front end (Revs).
- **Bisect an explanation with counters, not guesses.** Count each candidate cause separately
  in one run.
- **Instrument persistent state, not events,** when the event may already be under way. For
  example, read the stack to see a call in progress.
- **On a wrapping quantity, assert both ends.** A watermark that appears without the values
  before it was reached from the other side (Revs).

**Symbols and scripts**

- **A dropped probe symbol reads garbage that looks like data.** `--gc-sections` removed a
  counter, and gdb resolved the name into `.text`. Root every debugger-read symbol in the
  link (`-Wl,--undefined=`), and fail the link when one is missing (Revs, Vette); see the
  [port toolchain](port-toolchain.md). When a number is wrong by orders of magnitude, first
  check that you read the symbol you meant.
- **A gdb script aborts at the first unknown symbol.** "The trace stopped after the header"
  means the script is stale. Grep every `.gdb` file when you rename a global.
- **gdb names `$pc`, `$ps`, `$sp`, `$d0` and `$a0` are CPU registers.** `set $ps=…`
  corrupts SR. Name script variables `$sXxx` (Rescue on Fractalus, Revs).
- **Read the full output file, not the terminal.** A wrapper that ends with `tail` drops the
  header, which holds the sanity lines. Check the log belongs to the current run (Revs).

**Builds**

- **Prove the flags reached the build.** zsh does not word-split `$VAR`, so
  `make $COMMON X=1` passes one assignment. Use an array. `VAR+=` on the command line
  replaces the Makefile's list. Have the build print a fingerprint and assert it in the
  script, for example the probe-symbol count. A frame total that doesn't resemble the
  published baseline is the cheapest tell (Revs).
- **Clean after changing build flags or widely included headers.** A stale object reproduces
  the previous build's number to the digit (Revs, Rescue on Fractalus, Vette).
- **A run script is an instrument.** Sabotage it and fingerprint it before believing its
  output.
- **Record the binary hash per run.** Wait for one run to finish before starting the next. A
  killed batch left a stale binary that measured as a phantom regression. Identical results
  from a 120 s run and a 300 s run mean the machine stopped (Rescue on Fractalus).
- **Never rebuild an ELF that an emulator or oracle is using.** Freeze the executable and
  ELF for long runs, and never edit a launcher while it runs (Slicks, Pokeri).

**Snapshots and windows**

- **A frozen numerator over a live denominator prints a plausible lie.** When a window
  freezes its accumulators, snapshot every other counter at the window edge. Don't gate
  counters inside the hot loop; that moves the measurement (Revs).
- **A run that timed out is not a pass.** Every case needs an explicit success record and
  must reject loud stops (Vette, Alone in the Dark). Zero coverage fails rather than
  printing an empty measurement (Downwell).

**Analyses and reports**

- **A metric that improves because the tool got looser is worse than no number.** When a
  metric moves the way you want, check whether the thing changed or only the measuring
  (Revs: widening a resolver window took 5327 unexplained bytes to a fabricated zero).
- **A wrong static analysis still emits a confident ranked table.** Point a new analysis at
  a known case and require agreement first (Revs: two loop finders, both wrong).
- **A top-N report answers magnitude, not presence.** Ownership and dependency questions live
  in the tail. Print the whole distribution, group it by the thing being decided, and check
  that the groups partition the independently counted total (Revs).
- **Two runs of one instrument that disagree about a shared input** mean the instrument is
  defective.
- **A zero in a windowed census means "none in this window".** Widen the window before
  acting on an absence.

## 5. A/B discipline and baseline trajectories

**The control and the workload**

- **The control is the exact parent build, in the same session, on the same window and
  workload.** Never diff against a ledger row or another session's figure (Slicks, Rescue on
  Fractalus).
- **Pin the trajectory.** Use a fixed RNG seed for every performance run, and a fixed clock
  where the game allows it. Without them, render speed changes the trajectory and even the
  level: a 50 Hz interrupt asynchronous to the main loop shifts phase when the renderer
  speeds up. Never judge gameplay or rendering from a pinned build (Rescue on Fractalus,
  Revs).
- **A behaviour-preserving change must reproduce the final-state hash exactly** under the
  fixed clock. Real-time-clock runs cannot gate fidelity (Slicks).
- **A pinned seed pins the level, not the path.** Cross-build per-phase or per-iteration
  deltas carry about ±10% trajectory noise. Moving the start press 120 frames later, with no
  code change, moved a phase by the size of a filed "8% regression" (Rescue on Fractalus).
  Use phase tables for shares within one run, a whole-frame A/B or in-process differential
  for progress, and an in-process oracle for target-only changes.

**Windows and controls**

- **Bound windows in emulated fields, not host seconds.** Check that each arm actually
  reached the cap. Freeze on fields, not painted frames: at the cap, both arms have then
  simulated the same game time.
- **When the simulation steps once per painted frame, a faster arm simulates further** inside
  the same fields. For a change under about 2 ms, add a frame-matched control (Revs).
- **Built-in controls must not move.** Phases the change cannot touch should agree to about
  0.05 ms. When an untouched row moves, suspect the ISR landing elsewhere: quote neighbouring
  rows combined (Revs).
- **Size against the work, not the frame total.** The frame total moves in 20 ms steps, and
  the spin phase grows to absorb a saving. Use the sum of work phases excluding the spin, or
  the row you changed. The payoff is a step function: the last 1.5 ms before a field
  boundary can be worth +10% FPS (Revs).
- **If a change needs an enabling restructure, measure three builds:** the old code, the new
  code with the feature off, and the new code. Only the old code is the baseline (Revs: the
  feature's own switch read +34%, while the real change was +10.7%).
- **Know your noise floor before claiming.** End-to-end FPS differences under about 3% are
  agreement, not evidence. Run any baseline at least twice after a rebuild; an n=1 baseline
  produced a bogus "4% regression" (Rescue on Fractalus).
- **Layout moves timing.** Moving unrelated globals or sections changes alignment and beam
  phase. Pokeri saw 101 longword objects land on 2 mod 4 and measured 8% slower cold start;
  align them and audit it. A lowering step judged on ±0.7% layout noise selects lucky
  layouts, so use a layout-blind meter for such steps (Secret Weapons of Luftwaffe).
- **The same executable can show trajectory modes.** In Secret Weapons of Luftwaffe, run
  medians read 24.5 and 28.5 fields. Make per-step decisions on a deterministic
  fixed-workload meter.

**Workload**

- Measure while driving or flying, not parked: some counts run many times higher in motion.
- Keep practice, race, reset, crash and front-end windows distinct. Discard rows where the
  run stopped doing the measured work, for example a crash cinematic or the car leaving the
  track.
- Short windows hide bursts, such as synchronous generation in Downwell. Long windows dilute
  the scene.
- Cold first frames and steady-state frames are different measurements. Measure startup
  loading separately rather than dividing it across frames (Downwell).
- Measure on the default memory configuration. A run with expanded memory does not establish
  the baseline (Downwell: 512 KiB Chip).
- Suspect a beam-timing race? Re-run on a faster CPU, which moves a violation into the race
  window. Quote durations, not hit counts (Revs).

## 6. Pricing a change

**Before building**

- **Three numbers:** what the change deletes, what one unit of the new shape costs, and what
  it cannot touch. Two ports lost a built and proven optimisation to the missing third
  (Vette, Revs).
- **Price the prize before building it:** reachable share × removable fraction, compared with
  the noise floor. A skip scheme needs the visits removed *and* the cost of one visit in the
  new shape; compute the break-even (Revs: 39.5% of visits were 2.4% of the frame).
- **Name the quantity the cost is proportional to,** and check that the change reduces it.
  Direct-to-bitplane plotting cut stores, but the loop's cost was source reads. It came out
  9% slower (Revs).
- **Check whether a cheaper change already took the prize.** Two optimisations can compete
  for one saving.
- **Read what the worst case is made of before tightening its loop.** The largest wins were
  work not done.
- **Lever order:** do less work (skip unchanged work, fewer items), then change the
  representation, then code shape and assembly last.
- **Clean up the C before proposing assembly.** Read the target instructions and measure the
  whole affected path. Source size and instruction count don't price it (Revs).

**What does and doesn't count**

- **Deferring is not removing.** Price the flush minus the record. Work done inside a
  blitter or DMA shadow pays only for the part that exceeds the shadow (Rescue on
  Fractalus).
- **Divide by the right denominator.** Count how often a loop runs before pricing it per
  iteration. A per-body instruction census counts inline copies, so rank by instructions
  ÷ inline copies × a counted call rate (Revs).
- **Measure both the removed work and the replacement cost.** Never attribute a residual to
  an unmeasured component.
- **The recipe that broke a "structural" ceiling** (−36% on Rescue on Fractalus'
  rasteriser): shape-probe the inputs, prove the algebra on the host over millions of random
  cases, write the assembly, then run the on-target differential against the same C oracle.
  After special-casing a recursion's leaves, re-price their parents.
- **A reject path is already at the floor.** Any "check before drawing" re-reads the byte
  the check was meant to avoid.
- **Estimates are upper bounds.** They have over-read by between one third and 6×.
- **The 68020 cost model in Secret Weapons of Luftwaffe** charged about 1.1 cycles per code
  byte plus data accesses. Price in executed bytes, data accesses and taken branches, not
  instruction count.
- **Compare with the original only on a matched workload,** including the original
  platform's system and display services. A port-only stage (C2P) is not a slowdown "versus
  the original" (Vette).
- **An isolated routine win may not show in the whole workload;** the whole-workload A/B
  decides (Pokeri: a 5.48 µs dispatch saving gave no card gain).

## 7. The experiment loop

1. Build and run a quick correctness smoke test (the routine oracle).
2. Time against the parent. Reject a clear regression now and record one line.
3. A promising candidate earns the full fidelity gates (see the
   [validation harness](validation-harness.md)).
4. Confirm the final timing, then commit.

Never pay for full validation of a candidate already rejected on performance (Slicks).

**Reference switches.** Keep the old path behind a build switch while it serves as a paired
measurement or pixel/replay oracle. Profile scripts restore the normal build when they
finish, on success or failure. Never ship a reference switch (Downwell, Vette).

**What counts as a null.** A null counts only if the change ran (a positive-control counter),
was emitted (check the objdump) and was faithful. It proves this shape dead, not the
hypothesis false. A change that measured zero by FPS alone was never shown to be worth zero
milliseconds (Revs).

**Recording dispositions.** Keep or revert on the number: validated but slower is reverted.
Record each disposition in one line with its reason, and write "do not retry" at the code.
Read the measured dead ends before retrying, and require a changed premise and a new
measurement (Slicks, Pokeri, Revs, Rescue on Fractalus).

**Build behind a switch, measure, let the number decide.** Keep the machinery if its oracle
is reusable, and say plainly that it did not ship.

## 8. Budgets

- **Frame:** 20 ms (312 lines) per PAL frame at 50 Hz. Decide with the user whether the mean,
  p95 or maximum must meet it, and on which workload. At 7 MHz, spending 10 ms on anything is
  half the budget.
- **ISR:** a separate, fixed tax on all wall-clock time, capped at one frame. Over that, a
  displayed frame drops, and the player sees the stall, not the cost. Copper and pointer work
  go first, bounded work after. ISR time hides inside the phase it interrupted. Its
  per-firing total is one of the few legitimately cross-build numbers. Cache-gated parts of
  it still carry trajectory noise (Revs, Rescue on Fractalus).
- **Memory:** measure, don't reserve. Report Chip separately from the rest, and check before
  adding tables (Rescue on Fractalus: 675 KB in use, about 170 KB of it Chip-mandatory, so it
  needs 1 MB).
- **Game speed against frame rate:** when the original's speed depends on its frame rate,
  decouple it. Then the worst-case frame time stops being a ship blocker (Slicks: 33–48
  became 46–50 updates/s). See
  [fixed-time simulation](../playbooks/fixed-time-simulation.md).
- **Scene transitions:** judge them by overall latency and visible stalls, not per-frame
  limits (Downwell).

## 9. When to stop

- **The bar is met.** Do not reopen a closed candidate for margin (Rescue on Fractalus).
- **The profile is flat and experiments move totals by 0.03–1%.** Change the structure or
  declare the scope (Slicks: no routine above 7%).
- **"Closed" means measured at about zero or negative,** not pessimism about small numbers.
  Five or six honest 5-point wins reach a 1.2× gap (Rescue on Fractalus).
- **Below the instrument's resolution,** stop re-running for a better number. Use the static
  count or the differential as the evidence.
- **"At its floor" covers only the named operations.** Re-check the surrounding call and
  counter shape before closing.

## 10. Reporting

- Name the build (commit and flags), the harness, the window and the workload with every
  number. Never quote the better of two runs.
- Mark the evidence level: MEASURED, DERIVED or INFERRED. A plausible name or estimate is
  not a fact (Pokeri, Vette, Revs).
- A figure in an older note or commit is wrong by default. Delete obsolete figures rather
  than annotating them.
- Quote the in-session A/B or the differential ratio as the win, and FPS only as the
  standing baseline.
- Keep current measurements and one-line dispositions in the project's performance doc.
  Investigation logs belong in git history.

## Shared instruction-profile reader

`amigaxdev.aprof.parse_profile` reads `AITDPROF 1` flat-PC and call-node records;
`call_tree` supplies child lists, traversal order and inclusive totals. Consumers
retain their own symbols, buckets and workload denominators. The parser requires
flat-PC time plus gap/high time to equal node self-time. Elapsed time may exceed
that accounting by an aligned tail of at most one `CYCLE_UNIT`: profiler stop
prints the current clock without charging the last gap to an instruction. The
reader reports `header['tail']` separately; it never assigns it to a function.
`python3 scripts/test_aprof.py` tests zero, partial and full-clock stop tails,
accounting corruption, overflow and malformed trees.

A structurally valid tree is not proof of correct dynamic return pairing.
Unmatched RTS/RTE counters remain visible. `require_return_pairing(header)`
rejects missing/nonzero return diagnostics or overflow; consumers must also
establish workload-specific completion before claiming paired inclusive or
active-work costs. Historical approximate opening reports retain their explicit
qualification and are not promoted to exact call-tree evidence. Frame rows and
actual publications can have different phase boundaries; consumers must state
which denominator they use and retain it in before/after comparisons.
