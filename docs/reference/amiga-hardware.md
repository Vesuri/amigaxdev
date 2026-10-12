# Amiga hardware and OS for a port

Target-side rules the ports paid for, merged from Rescue on Fractalus, Revs, Slicks, Vette,
Pokeri, Alone in the Dark, Downwell, Secret Weapons of Luftwaffe and Stunt Car Racer. Read the
matching section before writing a copper list, a sprite, an interrupt handler, the takeover or
an audio driver. Numbers tagged **[000]** were measured on a 68000/OCS A500; re-measure them on
other targets. CPU code generation is in [68k optimisation](m68k-optimisation.md); emulator
use in [headless FS-UAE](headless-fsuae.md); building in [port toolchain](port-toolchain.md).

1. [Reference material](#reference-material)
2. [Targets](#targets)
3. [The Chip bus](#the-chip-bus)
4. [Memory](#memory)
5. [OS takeover and return](#os-takeover-and-return)
6. [Interrupts](#interrupts)
7. [Copper](#copper)
8. [Sprites](#sprites)
9. [Dual playfield](#dual-playfield)
10. [Write-only registers](#write-only-registers)
11. [AGA display and palette](#aga-display-and-palette)
12. [Chunky-to-planar, buffering and frame pacing](#chunky-to-planar-buffering-and-frame-pacing)
13. [Blitter](#blitter)
14. [Paula audio](#paula-audio)
15. [Input](#input)
16. [Files, WHDLoad and the OS lifecycle](#files-whdload-and-the-os-lifecycle)
17. [The dA JoRMaS framework](#the-da-jormas-framework)
18. [Compiler traps in hardware code](#compiler-traps-in-hardware-code)

## Reference material

AmigaXDev installs these ([environment](../environment.md)):

| What | Where |
|---|---|
| Hardware Reference Manual (OCS/ECS) as web pages | `$ADCD/HTML/Hardware_Manual.html`; chapters: 2 Copper, 3 Playfields (dual playfield, scrolling), 4 Sprites, 5 Audio (state machine, direct output), 6 Blitter (speed, system DMA), 7 System control (priorities, beam position, interrupts), F CIAs, G Keyboard |
| The same as AmigaGuide | `$ADCD/ROM_Kernel_Manuals/Hardware_Manual` |
| Libraries and Devices manuals, autodocs, includes | `$ADCD/HTML/Libraries_Manual.html`, `Devices_Manual.html`, `I_and_A_3.5.html`; `$ADCD/Includes_and_Autodocs_3.5` |
| AGA registers (FMODE, BPLCON3 banks, 24-bit colour) | `$AGA_GUIDE` |
| Kalms C2P routines | `$AMIGA_SHARE/kalms-c2p` |
| WHDLoad autodocs (`resload_*`, flags) | `$WHDLOAD`'s developer package `Docs/` |

## Targets

| | A500 (68000, OCS/ECS) | A1200 (68020, AGA) |
|---|---|---|
| Ports | Rescue on Fractalus, Revs, Downwell, Stunt Car Racer | Slicks, Vette, Pokeri, Alone in the Dark, Secret Weapons of Luftwaffe |
| Memory to design for | 512 KiB–1 MiB Chip, assume no real Fast RAM | 2 MiB Chip, no Fast RAM (WHDLoad adds none unless the slave asks) |
| Compiler | `-m68000`; no 32-bit mul/div | `-m68020 -msoft-float` (Alone in the Dark adds `-mtune=68020`) |
| Display | Up to 4 lores planes cost the CPU nothing ([Chip bus](#the-chip-bus)) | 8 planes; FMODE 3 wide fetches whenever the alignment allows ([Chip bus](#the-chip-bus)) |

- **Detect AGA with `GfxBase->ChipRevBits0 & GFXF_AA_LISA`.** On Kickstart 3.1 the AA bits are
  set only after `SetPatch`, so every boot path (Shell, Workbench, the slave) runs `SetPatch`
  first; otherwise an A1200 silently takes the OCS path (Slicks, Rescue on Fractalus). Some
  Kickstarts expose only the internal MLISA flag (`$13` measured on an A1200): Pokeri requires
  both `GFXF_AA_ALICE` and `GFXF_AA_LISA`, or falls back to the chip IDs (Lisa `$F8` in `LISAID`
  `$DFF07C`, Alice in `VPOSR`), never the CPU type. Keep an ECS path if the port supports it
  (Pokeri).
- Code that must stay correct on accelerated machines must not rely on 24-bit addresses: Stunt
  Car Racer tags the top byte of pointers (`and.l #$00FFFFFF`), which breaks when a buffer lands
  in 32-bit Fast RAM at `$01000000` or above. Keep such buffers in Chip RAM, or separate flags
  from pointers.
- Re-run beam-deadline checks on a fast CPU (`--cpu=68040`): a slow CPU publishes late and hides
  early writes ([Copper](#copper)).

## The Chip bus

- **The CPU, blitter, copper and display DMA share the Chip bus.** On a 68000 every CPU access is
  a Chip-bus access; on a Chip-only A1200 every data access and every instruction fetched outside
  the 256-byte cache is one.
- **Up to four lores bitplanes cost the 68000 nothing**: the 68000 uses only every other Chip-bus
  slot, and up to four lores planes fetch only in the slots it leaves (Hardware Reference Manual
  chapter 6, "Blitter Operations and System DMA"). Below five lores planes the question is Chip
  RAM, not cycles; Revs went from two to four planes for 16.6 KB and no cycles. Five or six lores
  planes, or hires, take CPU slots.
- **On AGA, fetch bitplanes 64 bits wide (`FMODE` = 3) whenever the screen can meet the
  alignment rules below.** FMODE sets the width of each bitplane fetch: 16 bits (0), 32 (1 or 2)
  or 64 (3). The display needs the same data either way, so wider fetches take a quarter of the
  Chip-bus slots and leave the rest to the CPU, blitter and copper. At FMODE 0 each lores plane
  takes one slot in eight: eight lores planes take every slot of a fetched line, and four hires
  planes do the same. It pays most with five or more lores planes (or three or more hires) and
  Chip-bound code; with four or fewer lores planes the CPU already has its slots and only blitter-
  and copper-heavy code gains. It does nothing for code that rarely touches Chip RAM, or outside
  the fetch window. Alone in the Dark's eight-plane book screen went from 88.5 to 69.0 ms per step
  (Chip-bus time 26.5 → 8.08 ms) on FMODE 3 alone; its gameplay, which is not Chip-bound, stayed
  at about 100 ms per frame. Alone in the Dark and Slicks (eight lores planes), Pokeri (four
  hires planes) and Secret Weapons of Luftwaffe run FMODE 3; Vette pins FMODE 0 on purpose so an
  A1200 fetches like an A500.
- **What FMODE 3 requires:**
  - every bitplane pointer on an 8-byte boundary, checked in code (Alone in the Dark
    `static_assert`s the picture size and checks its buffers at run time);
  - a fetched width that is a multiple of 64 pixels, and modulos that keep every row 8-byte
    aligned. The displayed width need not be: Pokeri shows 608 hires pixels from 640-pixel rows
    and masks the padding with the display window;
  - its own `DDFSTRT`/`DDFSTOP`: the OCS formulas do not apply. Alone in the Dark's 320-pixel lores
    window moved from `$38/$d0` to `$20/$98`; Pokeri's hires window fetches `$38..$c8` on AGA
    against `$3c..$cc` on ECS. The framework's AGA branch is an unmeasured donor pair,
    so derive the values for your width and validate the picture ([AGA display and
    palette](#aga-display-and-palette));
  - coarser hardware scrolling: at 64-bit fetch a smooth horizontal scroll needs the extra AGA
    scroll bits in `BPLCON1` and a fetch window that starts earlier;
  - an OCS/ECS path that writes FMODE 0 (detect AGA as in [Targets](#targets)).

  FMODE bits 2–3 set the sprite fetch width separately; writing 3 leaves sprites at 16 bits.
  Write FMODE with the rest of the mode, on both paths, never inherit it: nothing guarantees what
  the last OS screen left there.
- CPU reads of blitter targets wait for pending blits ([Blitter](#blitter)).

## Memory

- **`MEMF_CHIP` only for what DMA reads**: bitplanes, copper lists, sprites, Paula samples,
  blitter operands. Everything else `MEMF_ANY`, so it uses Fast RAM when present (Pokeri,
  Slicks, Downwell).
- **Reserve all game memory at startup, all-or-nothing**; no Exec allocation after the startup
  checkpoint. Allocate large blocks before many small ones (Slicks).
- **`__chip` static initialisers are discarded**: `.MEMF_CHIP` is a BSS hunk. Fill Chip data at
  runtime and guard it in the link audit (Rescue on Fractalus: a waveform became silence).
- **The stack is small.** A Shell task gets the default 4 KiB stack; big buffers go in BSS or the
  heap. Downwell corrupted an asset cache below the stack with an 800-byte automatic buffer
  (the same binary passed with 16 KiB); its verifier now checks a 256-byte canary at the stack
  bottom. Alone in the Dark measured a 6 KiB system stack under FS-UAE for code running in
  exception/trap context and must leave room for the whole interrupt chain; a 32-byte margin
  corrupted Exec during a VBI.
- **Keep the original pointer when aligning**, and free that pointer with the same size
  (Pokeri).
- **Wide AGA fetches need 8-byte-aligned plane pointers** and rows padded to the fetch unit
  (Pokeri pads to 640 px and allocates +8 bytes).
- **Audit allocations from the host**: AllocMem/FreeMem breakpoints across repeat launches and a
  low-Chip run (caught a per-launch leak in Slicks). To measure transient Chip residency, watch
  Exec's Chip `MemHeader.mh_Free` from gdb for the low-water mark and walk the free list at
  checkpoints for the largest block (Downwell). Debugger stops make these runs useless for
  timing.

## OS takeover and return

The ports take the machine over: per-line copper work and direct Paula need it, and an OS screen
re-inserts the system copper list after every `WaitTOF`.

**Takeover order** (Slicks, restore-checked):

1. Save `ActiView`, `GfxBase->copinit`, `DMACONR`, `INTENAR`.
2. `LoadView(NULL)`, `WaitTOF` twice.
3. `INTENA`/`INTREQ` = `$7fff`; all DMA off.
4. Swap the VERTB vector under `Disable` ([Interrupts](#interrupts)).
5. Install your copper list **with display DMA off**, then enable DMA `MASTER|COPPER|RASTER`
   (copper last). Otherwise an OS copper frame intermittently resets one-time register writes
   (Revs).
6. `INTENA` = `INTEN|VERTB|PORTS`.
7. `Forbid` for the whole run. Nothing inside may `Wait`; library opens/closes and `WaitTOF`
   pairs stay outside (Revs).

**Return order** (Slicks, Vette):

1. Stop your own interrupts and DMA.
2. `COP1LC` = saved `copinit`, strobe `COPJMP1`; `BPLCON3` = `$0c00` on AGA; copper DMA on.
3. Drain the blitter; restore the VERTB vector.
4. Clear everything, then restore the exact saved `DMACON`/`INTENA`.
5. `Permit`; `LoadView(saved)`, `WaitTOF` twice.
6. Free display memory only after DMA has stopped. `LoadView` restores neither `COP1LC` nor
   DMA; freeing first returned to an all-white Workbench (Vette).

- **Prove the return with readable state**: `ActiView`, the vector, `DMACONR`, `INTENAR`
  (`COP1LC` is write-only). Slicks has a restore-check target.
- **Leave sprite DMA off unless sprites are used**; if used, point idle channels at an empty
  sprite every frame (Slicks, Vette, Downwell).
- **For disk I/O, hand back interrupts, not the display**: restore the VERTB vector, saved
  `INTENA`, `DISK|BLITTER` DMA and the keyboard ICR, then `Permit`; keep `LoadView(NULL)` and your
  copper/raster DMA, and reverse on return. `WaitTOF` works in this window and a loading panel
  stays on screen (Slicks).

## Interrupts

- **Replace `SysBase->IntVects[INTB_VERTB]` (under `Disable`) instead of `AddIntServer`.** This
  drops graphics.library, gameport.device and timer.device off the vblank: ~780 µs a frame,
  3.9% of wall clock [000] (Revs; Vette and Slicks do the same). Keep an `AddIntServer` build
  for bisecting. Consequences:
  - The handler clears `INTREQ` VERTB itself, or level 3 re-triggers forever.
  - `WaitTOF` is dead while the vector is yours (graphics.library's server signals it). Wait on
    your own vblank counter, and restore the vector before the closing `LoadView`/`WaitTOF`.
- **Leave PORTS (level 2) on Exec's chain; hook the keyboard through `ciaa.resource`.** Starving
  FS-UAE's host-filesystem trap server resets the emulated machine; leaving it costs ~0.3%
  [000] (Rescue on Fractalus).
- **Mask `INTF_BLIT` during takeover** unless you use an interrupt-driven blitter queue: each
  blit-done was a useless graphics.library dispatch, ~6 × 52 µs per render iteration [000]
  (Revs). Restore `INTENA` verbatim; the OS needs it for QBlit.
- **Publish objects to the interrupt handler only after they are fully built**, guarded by a flag
  set on the last line of `initialize()`, not a non-null pointer. A VBI during construction
  installed a half-built copper list and latched it: a black screen whose probes each read
  healthy but were mutually inconsistent (Revs).
- **VBI work stays well under one frame**; bracket it with `VPOSR`/`VHPOSR` reads. Overrun
  silently drops a displayed frame (Rescue on Fractalus: a 19.7 ms decode in the VBI).
- **Copper, bitplane and sprite publication run first in the VBI**, then input, then audio: a
  Paula restart can busy-wait and must not delay a beam-critical write (Revs, Vette,
  Alone in the Dark).
- **Never run the original's timer-driven game body inside the Amiga interrupt.** The VBI counts
  ticks and updates time, input and Paula; the main loop runs the original's handlers at points
  where the engine is provably not drawing (Revs: 238 bad frames → 0; Vette, Pokeri and
  Alone in the Dark run original callbacks only at safe return points).
- **Derive a PC timer from the beam**: `vblank_count * 313 + line`, re-read until the count and
  `VPOSR` agree; a read just after line 0 that looks backwards is zero elapsed. BIOS ticks:
  accumulate 1193182 per VBI and tick every 65536 × 50 (exact at the 15625 Hz line rate)
  (Slicks). Game timing in general: [fixed-time simulation](../playbooks/fixed-time-simulation.md).
- Main-loop/interrupt shared state goes under nested `Disable`/`Enable`; no interrupt handler
  allocates (Slicks, Pokeri).
- Under WHDLoad the VBR is moved and the real vector table belongs to WHDLoad; never assume
  vectors at 0. Exec `IntVects` takeover is unaffected (Pokeri). For exception vectors see
  [WHDLoad MMU](../playbooks/whdload-mmu.md#whdload-owns-the-real-vector-table).

## Copper

- **An all-zero copper word halts the copper** for the rest of the frame (`MOVE #0` to register
  `$000`). Symptom: the whole screen uses the top region's pointers and modulos, which looks like
  a geometry bug. Either prefill every list with copper NOPs (`$01FE0000`; the Revs/Vette
  framework constructor does) or write every slot up to the terminator and check the built
  length (Slicks' framework does not prefill). A NOP does not excuse an unwritten slot: when you
  add or move a slot, check both ends.
- **Slot 0 (`WAIT 16,0`) and the last slot (`WAIT 255,254`) belong to the constructor**;
  per-frame builders start at 1. A variable-length list terminates right after its content, or
  double-buffered lists run into stale tails and flicker.
- **Colour MOVEs take effect immediately** (there is no one-line latency). For a split at line R:
  `WAIT (R-1, $E0)` in the right border, then **pointers first** (a late pointer breaks the
  band; a late colour is a few-pixel edge), then colours. Keep the horizontal position in
  `$C0`–`$E2`. Six pointer MOVEs overrun ~16 px into the band's first line, so a colour that
  must hit the first pixel needs its own slot before the pointers.
- **One WAIT per scanline; drop zero-height bands.** A WAIT already satisfied runs its pointer
  writes into the visible area.
- **Never poke a live list's `BPLxPT` mid-frame**: a torn hi/lo pointer garbages a frame. Swap
  pointers in the VBI. Colour-only mid-frame pokes are tolerable.
- **"In the VBI" is not "in the blank".** A handler that does game work first reaches the swap
  late (Revs: 49 of 49 presents at lines 46–149). A rewritten WAIT whose line is behind the beam
  blocks the copper until the next field and skips every later band. Do copper work first, stamp
  the beam line at every publication and keep a standing "late" counter that must read 0. A
  frame-boundary dump cannot see this (twelve clean captures preceded a broken screen).
- **Sprite pointers have an earlier deadline**: the copper writes `SPRxPT` at the list's first
  WAIT (line 16 in this layout) and sprite control words are fetched around line 25, so both must
  be final before then. A slow A500 render hides a violation; a 68040 exposed it (Rescue on
  Fractalus: 31 of 32 advances at line ≤ 16 on a 68040, zero violations reported on an A1200).
- **A list whose pointers move must be double-buffered**: build the inactive one, then `COP1LC`
  + `COPJMP1` in the VBI; never edit the active list. Drop "last value written" caches: they
  compare against the live list while you write the stale back one. An immediate `COPJMP1` is
  safe only at vblank (Vette measured all handoffs at lines 1–3 on 68020/030/040); mid-frame it
  smears sprites.
- **Alternative handoff**: write `COP1LC` without `COPJMP1` from the main thread at safe lines,
  and retire the old buffer at the next VBI; a late interrupt can then never restart a list
  mid-screen (Pokeri).
- Install a list built during a frame at the end of that render, never partway through.
- Bitmap height equals the number of lines the copper gives its region.
- **Hardware scrolling by pointer**: a circular bitplane whose pointers advance each line scrolls
  vertically with no copying; refill hidden lookahead rows in blocks (Downwell).

## Sprites

- **Chaining reuses a channel without copper writes**: `[ctrlA][dataA][ctrlB][dataB][0,0]` in one
  buffer; after VSTOP the DMA reads the next control words. The second VSTART must be **strictly
  greater** than the first VSTOP (Revs). Double-buffering a chained channel duplicates the whole
  chain; mirror the control words per frame rather than copying the block (that was ~1% of wall
  clock).
- **Sprite pair 0/1 uses COLOR17–19 (`$1A2`/`$1A4`/`$1A6`)**, pair 2/3 COLOR21–23 (`$1AA`…), every
  eight bytes. COLOR16 (`$1A0`) is never displayed by a sprite; writing pens from `$1A0` puts every
  colour one register low (Revs).
- **HSTART is `$80 + x`** for a playfield whose first pixel is at DIWSTRT's `$81`; `$81 + x` is one
  lores pixel right (measured, Revs). `HSTART = ((SPRxPOS & $FF) << 1) | (SPRxCTL & 1)`. Fit the
  offset from a dumped plane buffer composed with the sprite words, not by eye.
- **Over a pen-0 playfield pixel a sprite wins at every `BPLCON2` value.** Priority cannot hide a
  sprite where the playfield draws nothing; blank the sprite's pen or end it.
- Lower-numbered channels cover higher ones; assign parts front-to-back in the original painter
  order (Downwell).

## Dual playfield

- **PF1 is the odd planes (1/3/5), PF2 the even (2/4/6), and so are the modulos** (`BPL1MOD`,
  `BPL2MOD`). Two independent interleaved bitmaps, one per playfield, each need only their own
  modulo, and each layer keeps its own buffering: Revs double-buffers terrain on PF1 and
  single-buffers its cockpit on PF2, rewriting only PF1's pointers at the swap.
- **PF2's pen 0 is transparent and PF1's is the background** (COLOR00), so PF1 has four colours
  and PF2 three. With two planes each, PF1 is COLOR00–03 and PF2 COLOR08–11; COLOR08 is never
  displayed. Count the colours in each region before deciding the split (Revs remapped one source
  pen to fit PF2).
- `BPLCON2` bit 6 (`PF2PRI`, `$0040`) puts PF2 in front; it is inert without `DBLPF`.
- **A pen-level oracle cannot see a wrong colour register.** Read the copper back and check each
  PF2 register against its PF1 partner.

## Write-only registers

- **Every write-only display register (`BPLCON2`, …) is scene state with a named owner.** A list
  that does not write `$104` inherits whatever the previous scene left (Rescue on Fractalus: a
  gauge drawn over the cockpit, but only after a scene change). Program sprite and playfield
  priority explicitly; never depend on the OS value (Downwell).
- **`PFxP = 0` is playfield in front of every sprite**; `PFxP = N` is behind groups 0..N-1;
  `PFxP = 4` (`BPLCON2 = $0024`, what Intuition and the framework's `setPlayfield` write) is every
  sprite in front. Revs had both arms of an `#ifdef` inverted.
- **Never cache a write-only register's value**; one 16-bit store is cheaper than reasoning about
  who wrote it last.
- A 68000 read of `$DFF104` returns the floating bus; gdb's read under FS-UAE returns the stored
  value. Cross-check with `BPLCON0` (`$DFF100`). Use two marker functions rather than one with a
  tag argument: a breakpoint fires at entry, before the body records the tag.

## AGA display and palette

- **Reuse a proven mode and validate the words it writes.** Slicks' 320×200×8 mode: FMODE 3,
  interleaved 320-byte rows, `BPL1MOD`/`BPL2MOD` 280, `DIWSTRT` `$3881`, `DIWSTOP` `$00c1`,
  `DIWHIGH` `$2100`. The framework's AGA data-fetch branch is otherwise unverified.
- **`DIWHIGH` is always written, never inherited**; DIW is in lores, non-interlaced units.
- **Clear `BPLCON4` (`$10C`) on AGA**: an inherited bitplane XOR value remaps every pen
  (Pokeri writes 0 in its list).
- **Interleave the bitmap so chunky and planar share the row offset** (`y * 320`): one multiply
  serves both (Slicks).
- **A 24-bit colour is two MOVEs**: high nibbles, then `BPLCON3` LOCT (`$0200`) low nibbles, with
  a bank switch every 32 colours; restore bank 0 with LOCT clear. A 256-colour load is ~528 MOVEs
  (Slicks' list is 558 longs). VGA 6-bit to 8-bit is `v << 2 | v >> 4`. Alone in the Dark uses a
  measured transfer table rather than a fitted gamma.
- **Record each colour MOVE's slot once and patch words in place** for palette changes; rebuild a
  list only after waiting for display blank, and apply queued palette changes at publication time
  (a mid-frame change splits one frame) (Slicks).
- Keep sprite palette setup from overwriting the 256 game colours (Alone in the Dark).

## Chunky-to-planar, buffering and frame pacing

- **Full rows: Kalms `c2p1x1_8_c5_bm`** (width a multiple of 32, x a multiple of 8); it reads 32
  bytes past the source, so allocate +32 (Slicks). Alone in the Dark calls
  `c2p1x1_8_c5_gen` per dirty row through a C ABI wrapper. Record the pinned upstream revision.
- **Dirty rectangles**: 16-pixel aligned, merged on overlap, bounded; overflow unions, never
  drops (Slicks). Combine a frame's bounds *before* C2P alignment, so separately aligned strips
  don't overlap (Alone in the Dark). Compute bounds from what was drawn, never from shadow
  comparisons (Vette, Alone in the Dark). For sparse updates Slicks' 16-pixel C2P stores only
  final plane words and sparse pixels use per-pixel `BFINS`; 8-pixel and hybrid C2P gave no
  gain.
- **Verify a C2P against a bit-level reference, hooking every destination store**, which catches
  intermediate values written to the shown bitmap (Slicks). Keep the full-frame verifier out of
  speed measurements.
- **A double-buffered back buffer also converts the rectangles changed in the previous update**,
  or partial updates show two-frame-old pixels (Vette).
- **Single-buffered publication waits for the display-end edge** (line `$100`) as an edge, not a
  level; a late update publishes at once and missed slots are not queued (Slicks: 33–48 → 46–50
  updates/s, no visible tearing).
- **Pace completed frames, never drawing calls**: one wait and one publication per completed
  frame (Alone in the Dark).
- **Game time comes from a real-time clock in the original's units**, not a fixed credit per
  drawn frame, which runs slow motion when an update spans two frames (Slicks). On fast CPUs cap
  source-defined animation loops at one step per field (Vette). See
  [fixed-time simulation](../playbooks/fixed-time-simulation.md).
- **Double buffering costs a second bitmap (64,000 bytes at 320×200×8) and every dirty region
  twice**: decide on measured headroom (Slicks rejected it at ~95 KB free).

## Blitter

- **The blitter is a measured candidate, not free.** On an A500 it shares the bus with the CPU: a
  whole-row blitter paint was byte-exact and 2× slower; only blits that replace CPU work (a
  D-only clear) paid (Revs [000]). On faster CPUs it can become the bottleneck.
- **Drain before CPU access**: CPU reads of blit targets wait, and CPU writes, cache eviction,
  free and teardown all need the blitter idle (Pokeri).
- **Interleaved bitmaps multiply blit height by the plane count**; split tall blits (Pokeri: a
  4-plane 292-row clear needs two).
- **The first/last-word masks apply to channel A only.** For a masked blit of a constant pen, put
  the opacity mask on A and the pen pattern on B; with opacity on B, unaligned edges stay
  unmasked. Cover the whole fetch span with the edge masks, including a zero mask for a spill
  word (Downwell: 27 wrong HUD bytes until fixed).

## Paula audio

- **Four DMA channels; allocate them by explicit priority rules** and document where the port
  departs from the original (Slicks). Channels 0 and 3 are left, 1 and 2 right.
- **Period = 3546895 / Hz (PAL)**, clamp 124..65535; for higher rates use half- or quarter-rate
  loops prepared at load, with hysteresis (Slicks).
- Convert samples once at load into Chip RAM as signed 8-bit with the original's gain. Volume is
  linear 0..64: map relative levels, not RMS.
- **Paula has no one-shot mode**: start the sample, and one VBI later point the reload registers
  at a two-byte silent loop; expire by VBI counters (Slicks, Vette).
- **Keep DMA control in blanking**: stop in one VBI, program and start in the next. DMA control
  during display coincided with one-refresh horizontal strips in static scenery (Slicks; 20–40
  ms latency). If a restart must wait inline, wait at least two sample periods of the largest
  period since the stop (Vette, from the Hardware Reference Manual's audio state machine).
- **Protect note setup from the audio interrupt, not just DMA timing.** A pending request
  can consume a partially prepared attack/loop state before the new sample starts. Mask that
  channel during preparation and restore it only after the state and DMA startup are ready.
  The shared handler must intersect `INTREQR` with `INTENAR`: another channel can interrupt
  while the protected channel still has a pending request (Grand Prix Circuit).
- **Check actual sample starts as well as acknowledgements.** In GPC's 68030 capture, an
  interrupt race replaced 19 initial 2,250-word sample lengths with 550-word loop lengths;
  the A500 reference did not. Compare note commands, driver state and DMA fetches. Account
  for the startup fetch discarded by Agnus, and verify actual capture lengths: a requested
  600-field Barto capture returned only 100 fields in this backend. Use bounded chunks and
  do not assume register continuity across their boundaries.
- **Or leave all DMA on and silence with volume 0**: period and volume changes are then plain
  pokes and only a waveform change restarts (Revs).
- `AUDxLEN` counts words; pointer and length latch only at a loop wrap. Odd loops need an aligned
  copy; no header bytes inside a loop. Clear the pending audio interrupt before writing `AUDxDAT`
  for direct output (Vette).
- **The LED filter is on at boot** (~5 kHz low-pass); turn it off when the original had none
  (Revs).
- **Re-host synthesised sound chips as chip state driving Paula loops**, not per-note rendered
  banks: square waves at computed periods; noise from a rendered LFSR (Revs) or evolving buffers
  refreshed in slices (Pokeri). Envelopes clocked at 50 Hz quantise 100 Hz steps in pairs; a CIA
  timer fixes that. No port has re-hosted FM/OPL.
- Keep the refresh in the VBI and bounded in time, with no per-sample interrupt mixer (Pokeri).
  When the original drives more voices than it has channels, port its priority mixer and map
  its channels to Paula's, rather than mixing voices together (Rescue on Fractalus: 16 voice
  slots onto four POKEY channels).

## Input

- **Keyboard**: a CIA-A serial-port ICR handler via `AddICRVector`; if it returns the owner,
  remove theirs, add yours, restore on exit. Code = `ROR(~SDR, 1)`; the handshake holds SPMODE
  output ~85 µs. Clear modifier state at takeover: releases while the OS owned the keyboard never
  arrive (Slicks, Revs).
- **Keep a level map and an edge latch.** A level poll misses taps shorter than its period (Revs:
  ~37 ms); latch the down edge, consume it when the original reads it, expire after a few fields.
  Never feed held keys only through an event queue. **Deliver a press until the original actually
  reads it**: a generated input clock edge is not acknowledgement (Pokeri lost taps that way).
- One raw-key → original-code table; count unmapped codes. Emulate typematic repeat if the
  original relies on it (Slicks: 500 ms delay, 10.9/s).
- **Joystick**: `JOYxDAT` is crosswise quadrature (forward = b8^b9, left = b9, back = b0^b1,
  right = b1); fire is CIA-A PRA bit 7 (port 1) / bit 6 (port 0); button 2 is `POTINP` bit 14.
  Sample once per VBI. CD32 pads are a bit-banged read with interrupts off, detected over several
  spaced samples at boot (Rescue on Fractalus).
- **Mouse**: left = CIA-A PRA bit 6; right/middle = `POTINP` bits 10/8 after `POTGO = 0`, or they
  read held on real hardware (FS-UAE does not model this). `JOY0DAT` counters are 8-bit and wrap:
  take the delta every frame and confirm the sign with a real mouse (Revs).
- WHDLoad OS switches can clear held-key state; see
  [WHDLoad MMU](../playbooks/whdload-mmu.md#compatibility-structures-must-have-real-backing-storage).

## Files, WHDLoad and the OS lifecycle

- **Load before takeover**; touch the disk only at explicit boundaries inside an I/O window
  ([OS takeover](#os-takeover-and-return)).
- **Whole-file reads in one `Read`; saves rewrite the file in place in one write**, skipped when
  unchanged (CRC); no temp file, backup or rename. Each WHDLoad OS switch is a visible pause plus
  write delay (Slicks, Pokeri). Pre-create files that saves will overwrite: creating files under
  WHDLoad's write cache hung in low memory (Pokeri).
- **Handle Workbench startup yourself**: without `pr_CLI`, `WaitPort`/`GetMsg` the WBStartup
  before opening dos.library and reply last, under `Forbid`; the freestanding startup does
  neither (Vette). Take arguments with `GetArgStr` and data via `PROGDIR:`, identical under Shell,
  Workbench and the slave (Slicks).
- The shared `_start` ignores `main`'s return value; supply a start that preserves it (Pokeri).
- **Flush caches after writing code at runtime** (`CacheClearU()` natively, `resload_FlushCache`
  under WHDLoad): see [hardware debugging](../playbooks/new-game-playbook-hardware.md#flush-after-the-final-executable-write).
- **WHDLoad's quit key cannot run deferred saves**, and must not be a game key (Revs moved it off
  F10).
- Crash dumps, installer updates and release archives: [native port validation](../native-port-validation.md).

## The dA JoRMaS framework

The ports share a C++ hardware framework with two lineages; fixes do not carry over between them
automatically.

| Lineage | Ports | Differences |
|---|---|---|
| Template set | Rescue on Fractalus, Revs, Vette, Alone in the Dark | vasm asm bridges, copper NOP prefill, `setPlayfield` with Vette's interlace, window and hires fetch fixes |
| DanceDiverse3 set | Slicks, Secret Weapons of Luftwaffe | C++ bodies for GCC (`ASSEMBLER` undefined), AGA `setPlayfield` and 24-bit palette, no NOP prefill |

Pokeri and Downwell carry further-modified copies; check which lineage a fix came from before
porting it.

Every copy's `setPlayfield` writes FMODE 3 on AGA with the unmeasured fetch window from the
donor project. Ports with their own display owner override it (Vette writes FMODE 0, Alone in
the Dark and Pokeri write their own measured windows).

- `--gc-sections` hides dormant link traps until the first caller; partial-link the framework
  (`ld -r`) to see them. Vette found a bridge with no asm body and a helper pulling `__mulsi3`;
  the DanceDiverse3 copy declares `getVBR`, `isLongFrame`, `isBlitterBusy` and `blitterWait`
  without defining them.
- The non-interleaved asm arms of `Bitmap` were silent no-ops: treat interleaved as an invariant
  (Vette). The factories leaked Chip storage when a second allocation failed, and `Bitmap`
  allocated `width/8` while drawing at word-padded stride (Pokeri).
- The statically allocated blitter queue leaks 49,158 bytes per launch unless released at
  shutdown (Slicks).
- **Include every system header first and `AmigaHardware.h` last**: its bare register macros
  collide with `struct Custom` members.
- Record every local framework change in the project's `framework/` notes so it can be re-synced.

## Compiler traps in hardware code

- **`volatile` on every custom-chip pointer and interrupt-written flag**: `-O2` turned a
  blitter-queue wait into `bra.s .` and duplicated a `BLTSIZE` store (Rescue on Fractalus).
- Normalise asm `Scc` results (`$FF`) with `!= 0` before using them as `bool`: `!b` gave `$FE`
  (Pokeri).
- No function-local statics: they need `__cxa_guard_*`, which the freestanding runtime lacks
  (Vette). Build with `-fcheck-new` so a failed `new` returns null.
- A cross-object `bsr` is `R_68K_PC16`, which `elf2hunk` cannot represent; use `jsr` (Pokeri).
- Every global a debugger reads must be kept from `--gc-sections` (a `PROBE_SYMS` list), or its
  symbol resolves into instruction bytes (Vette, Alone in the Dark).
- `alignas(4)`, the mul/div audit and the other link audits: [port toolchain](port-toolchain.md)
  and [68k optimisation](m68k-optimisation.md#2-68000-versus-68020).
