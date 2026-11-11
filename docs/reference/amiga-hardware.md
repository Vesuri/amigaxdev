# Amiga hardware and OS for a port

Target-side rules learned from native ports to A500 and A1200 targets. Read the
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
17. [The shared framework](#the-shared-framework)
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
| Memory to design for | 512 KiB–1 MiB Chip, assume no real Fast RAM | 2 MiB Chip, no Fast RAM (WHDLoad adds none unless the slave asks) |
| Compiler | `-m68000`; no 32-bit mul/div | `-m68020 -msoft-float` (optionally `-mtune=68020`) |
| Display | Up to 4 lores planes cost the CPU nothing ([Chip bus](#the-chip-bus)) | 8 planes; FMODE 3 wide fetches whenever the alignment allows ([Chip bus](#the-chip-bus)) |

- **Detect AGA with `GfxBase->ChipRevBits0 & GFXF_AA_LISA`.** On Kickstart 3.1 the AA bits are
  set only after `SetPatch`, so every boot path (Shell, Workbench, the slave) runs `SetPatch`
  first; otherwise an A1200 silently takes the OCS path. A
  `kick31.s` slave gets the same `SetChipRev(SETCHIPREV_BEST)` from `INITAGA`; without it
  KickEmu reports `$13` and with it `$1F` (one port's HIRES pointer was halved without it). Some
  Kickstarts expose only the internal MLISA flag (`$13` measured on an A1200): require
  both `GFXF_AA_ALICE` and `GFXF_AA_LISA`, or fall back to the chip IDs (Lisa `$F8` in `LISAID`
  `$DFF07C`, Alice in `VPOSR`), never the CPU type. Keep an ECS path if the port supports it.
- Code that must stay correct on accelerated machines must not rely on 24-bit addresses: code
  that tags the top byte of pointers (`and.l #$00FFFFFF`) breaks when a buffer lands
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
  RAM, not cycles: going from two to four planes costs Chip RAM and no cycles. Five or six lores
  planes, or hires, take CPU slots.
- **On AGA, fetch bitplanes 64 bits wide (`FMODE` = 3) whenever the screen can meet the
  alignment rules below.** FMODE sets the width of each bitplane fetch: 16 bits (0), 32 (1 or 2)
  or 64 (3). The display needs the same data either way, so wider fetches take a quarter of the
  Chip-bus slots and leave the rest to the CPU, blitter and copper. At FMODE 0 each lores plane
  takes one slot in eight: eight lores planes take every slot of a fetched line, and four hires
  planes do the same. It pays most with five or more lores planes (or three or more hires) and
  Chip-bound code; with four or fewer lores planes the CPU already has its slots and only blitter-
  and copper-heavy code gains. It does nothing for code that rarely touches Chip RAM, or outside
  the fetch window. One Chip-bound eight-plane screen went from 88.5 to 69.0 ms per step
  (Chip-bus time 26.5 → 8.08 ms) on FMODE 3 alone, while gameplay that was not Chip-bound did
  not change. A port may pin FMODE 0 on purpose so an A1200 fetches like an A500.
- **What FMODE 3 requires:**
  - every bitplane pointer on an 8-byte boundary, checked in code (`static_assert` the
    picture size and check the buffers at run time);
  - a fetched width that is a multiple of 64 pixels, and modulos that keep every row 8-byte
    aligned. The displayed width need not be: 608 hires pixels can be shown from 640-pixel rows
    with the padding masked by the display window;
  - its own `DDFSTRT`/`DDFSTOP`: the OCS formulas do not apply. One measured hires window fetches
    `$38..$c8` on AGA against `$3c..$cc` on ECS. A 320-pixel lores window fetched from `$20/$98`
    works but its `$20` start costs sprites 3–7 (below); the same pixels at the same place come
    from `$38`/`$b0` with every sprite (checked in real video). The framework's AGA branch is an
    unmeasured pair. Derive the values for your width and validate the picture ([AGA display and
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
  blitter operands. Everything else `MEMF_ANY`, so it uses Fast RAM when present.
- **Reserve all game memory at startup, all-or-nothing**; no Exec allocation after the startup
  checkpoint. Allocate large blocks before many small ones.
- **`__chip` static initialisers are discarded**: `.MEMF_CHIP` is a BSS hunk. Fill Chip data at
  runtime and guard it in the link audit (otherwise, for example, a waveform becomes silence).
- **The stack is small.** A Shell task gets the default 4 KiB stack; big buffers go in BSS or the
  heap. An 800-byte automatic buffer corrupted an asset cache below the stack (the same binary
  passed with 16 KiB); check a 256-byte canary at the stack bottom in the verifier. Code running
  in exception/trap context measured a 6 KiB system stack under FS-UAE and must leave room for
  the whole interrupt chain; a 32-byte margin corrupted Exec during a VBI.
- **Keep the original pointer when aligning**, and free that pointer with the same size.
- **Wide AGA fetches need 8-byte-aligned plane pointers** and rows padded to the fetch unit
  (for example, pad to 640 px and allocate +8 bytes).
- **Audit allocations from the host**: AllocMem/FreeMem breakpoints across repeat launches and a
  low-Chip run (this catches per-launch leaks). To measure transient Chip residency, watch
  Exec's Chip `MemHeader.mh_Free` from gdb for the low-water mark and walk the free list at
  checkpoints for the largest block. Debugger stops make these runs useless for
  timing.

## OS takeover and return

The ports take the machine over: per-line copper work and direct Paula need it, and an OS screen
re-inserts the system copper list after every `WaitTOF`.

**Takeover order** (restore-checked):

1. Save `ActiView`, `GfxBase->copinit`, `DMACONR`, `INTENAR`.
2. `LoadView(NULL)`, `WaitTOF` twice.
3. `INTENA`/`INTREQ` = `$7fff`; all DMA off.
4. Swap the VERTB vector under `Disable` ([Interrupts](#interrupts)).
5. Install your copper list **with display DMA off**, then enable DMA `MASTER|COPPER|RASTER`
   (copper last). Otherwise an OS copper frame intermittently resets one-time register writes.
6. `INTENA` = `INTEN|VERTB|PORTS`.
7. `Forbid` for the whole run. Nothing inside may `Wait`; library opens/closes and `WaitTOF`
   pairs stay outside.

**Return order**:

1. Stop your own interrupts and DMA.
2. `COP1LC` = saved `copinit`, strobe `COPJMP1`; `BPLCON3` = `$0c00` on AGA; copper DMA on.
3. Drain the blitter; restore the VERTB vector.
4. Clear everything, then restore the exact saved `DMACON`/`INTENA`.
5. `Permit`; `LoadView(saved)`, `WaitTOF` twice.
6. Free display memory only after DMA has stopped. `LoadView` restores neither `COP1LC` nor
   DMA; freeing first returned to an all-white Workbench.

- **Prove the return with readable state**: `ActiView`, the vector, `DMACONR`, `INTENAR`
  (`COP1LC` is write-only), with a restore-check make target.
- **Leave sprite DMA off unless sprites are used**; if used, point idle channels at an empty
  sprite every frame.
- **For disk I/O, hand back interrupts, not the display**: restore the VERTB vector, saved
  `INTENA`, `DISK|BLITTER` DMA and the keyboard ICR, then `Permit`; keep `LoadView(NULL)` and your
  copper/raster DMA, and reverse on return. `WaitTOF` works in this window and a loading panel
  stays on screen.

## Interrupts

- **Replace `SysBase->IntVects[INTB_VERTB]` (under `Disable`) instead of `AddIntServer`.** This
  drops graphics.library, gameport.device and timer.device off the vblank: ~780 µs a frame,
  3.9% of wall clock [000]. Keep an `AddIntServer` build
  for bisecting. Consequences:
  - The handler clears `INTREQ` VERTB itself, or level 3 re-triggers forever.
  - `WaitTOF` is dead while the vector is yours (graphics.library's server signals it). Wait on
    your own vblank counter, and restore the vector before the closing `LoadView`/`WaitTOF`.
- **Leave PORTS (level 2) on Exec's chain; hook the keyboard through `ciaa.resource`.** Starving
  FS-UAE's host-filesystem trap server resets the emulated machine; leaving it costs ~0.3%
  [000].
- **Mask `INTF_BLIT` during takeover** unless you use an interrupt-driven blitter queue: each
  blit-done was a useless graphics.library dispatch, ~6 × 52 µs per render iteration [000].
  Restore `INTENA` verbatim; the OS needs it for QBlit.
- **Treat BLIT masking as scoped ownership, not a one-time boot setting.** Trace writes
  enabling bit 6 from boot through race entry, overlay reload, pause/resume, pits and menus.
  Prove both graphics.library QBlit/QBSBlit queues remain empty during the owned interval
  and audit other BLIT servers before masking it. In one slave a 68020+Fast trace had BLIT
  disabled, while accelerated profiles enabled it and paid for empty interrupts on every
  blit; one CPU's trace does not establish the others' state. Save the entry BLIT
  enable state, acquire at the rendering epoch and resume, and check INTENAR at draw entry
  for re-enables. Restore the owned bit on every exit, fault and unload, without overwriting
  unrelated interrupt changes. INTENA uses set/clear writes: writing a saved INTENAR value
  directly is not a restoration. Test lifecycle and injected-fault paths as well as racing.
- **Publish objects to the interrupt handler only after they are fully built**, guarded by a flag
  set on the last line of `initialize()`, not a non-null pointer. A VBI during construction
  installed a half-built copper list and latched it: a black screen whose probes each read
  healthy but were mutually inconsistent.
- **VBI work stays well under one frame**; bracket it with `VPOSR`/`VHPOSR` reads. Overrun
  silently drops a displayed frame (for example, a 19.7 ms decode in the VBI).
- **Copper, bitplane and sprite publication run first in the VBI**, then input, then audio: a
  Paula restart can busy-wait and must not delay a beam-critical write.
- **Never run the original's timer-driven game body inside the Amiga interrupt.** The VBI counts
  ticks and updates time, input and Paula; the main loop runs the original's handlers at points
  where the engine is provably not drawing (one port went from 238 bad frames to 0). Run
  original callbacks only at safe return points.
- **Derive a PC timer from the beam**: `vblank_count * 313 + line`, re-read until the count and
  `VPOSR` agree; a read just after line 0 that looks backwards is zero elapsed. BIOS ticks:
  accumulate 1193182 per VBI and tick every 65536 × 50 (exact at the 15625 Hz line rate)
  Game timing in general: [fixed-time simulation](../playbooks/fixed-time-simulation.md).
- Main-loop/interrupt shared state goes under nested `Disable`/`Enable`; no interrupt handler
  allocates.
- Under WHDLoad the VBR is moved and the real vector table belongs to WHDLoad; never assume
  vectors at 0. Exec `IntVects` takeover is unaffected. For exception vectors see
  [WHDLoad MMU](../playbooks/whdload-mmu.md#whdload-owns-the-real-vector-table).

## Copper

- **An all-zero copper word halts the copper** for the rest of the frame (`MOVE #0` to register
  `$000`). Symptom: the whole screen uses the top region's pointers and modulos, which looks like
  a geometry bug. Either prefill every list with copper NOPs (`$01FE0000`; the framework's
  `CopperList` constructor does) or write every slot up to the terminator and check the built
  length. A NOP does not excuse an unwritten slot: when you
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
  late (one port measured 49 of 49 presents at lines 46–149). A rewritten WAIT whose line is behind the beam
  blocks the copper until the next field and skips every later band. Do copper work first, stamp
  the beam line at every publication and keep a standing "late" counter that must read 0. A
  frame-boundary dump cannot see this (twelve clean captures preceded a broken screen).
- **Sprite pointers have an earlier deadline**: the copper writes `SPRxPT` at the list's first
  WAIT (line 16 in this layout) and sprite control words are fetched around line 25, so both must
  be final before then. A slow A500 render hides a violation; a 68040 exposes it (31 of 32
  advances at line ≤ 16 on a 68040 in one port, with zero violations reported on an A1200).
- **A list whose pointers move must be double-buffered**: build the inactive one, then `COP1LC`
  + `COPJMP1` in the VBI; never edit the active list. Drop "last value written" caches: they
  compare against the live list while you write the stale back one. An immediate `COPJMP1` is
  safe only at vblank (all handoffs measured at lines 1–3 on 68020/030/040); mid-frame it
  smears sprites.
- **Alternative handoff**: write `COP1LC` without `COPJMP1` from the main thread at safe lines,
  and retire the old buffer at the next VBI; a late interrupt can then never restart a list
  mid-screen.
- Install a list built during a frame at the end of that render, never partway through.
- Bitmap height equals the number of lines the copper gives its region.
- **Hardware scrolling by pointer**: a circular bitplane whose pointers advance each line scrolls
  vertically with no copying; refill hidden lookahead rows in blocks.

## Sprites

- **Chaining reuses a channel without copper writes**: `[ctrlA][dataA][ctrlB][dataB][0,0]` in one
  buffer; after VSTOP the DMA reads the next control words. The second VSTART must be **strictly
  greater** than the first VSTOP. Double-buffering a chained channel duplicates the whole
  chain; mirror the control words per frame rather than copying the block (that was ~1% of wall
  clock).
- **Sprite pair 0/1 uses COLOR17–19 (`$1A2`/`$1A4`/`$1A6`)**, pair 2/3 COLOR21–23 (`$1AA`…), every
  eight bytes. COLOR16 (`$1A0`) is never displayed by a sprite; writing pens from `$1A0` puts every
  colour one register low.
- **HSTART is `$80 + x`** for a playfield whose first pixel is at DIWSTRT's `$81`; `$81 + x` is one
  lores pixel right (measured). `HSTART = ((SPRxPOS & $FF) << 1) | (SPRxCTL & 1)`. Fit the
  offset from a dumped plane buffer composed with the sprite words, not by eye; then confirm
  in the real video (below).
- **Over a pen-0 playfield pixel a sprite wins at every `BPLCON2` value.** Priority cannot hide a
  sprite where the playfield draws nothing; blank the sprite's pen or end it.
- Lower-numbered channels cover higher ones; assign parts front-to-back in the original painter
  order.
- **AGA sprite colours come from a 16-entry bank** (`BPLCON4` bits 7–4 even sprites, 3–0 odd):
  entry `bank·16 + 4·(pair & 3) + colour`, so with bank `F` pair 4/5 shows `F9`–`FB` and 6/7
  `FD`–`FF`. In a 256-colour game no bank is free: census the entries actually displayed on
  every screen the sprite appears on, give each exact game colour its own channel (sprite 6
  colour 2 = `FE`), and steal one never-displayed entry for the rest, set only in frames that
  show the sprite (for example, a mouse pointer on `F9`).
- **Bitplane DMA from `DDFSTRT` on takes the sprite slots there**: sprite n fetches at
  `$15+4n`/`$17+4n`, so `$20` leaves sprites 0–2 and `$30` costs sprite 7. A channel without
  its slots showed as a fixed-width block that moved only vertically (the framework's AGA
  `$20`). Composing dumped sprite words over the planes cannot see this: check sprites in
  the emulator's real video (a one-field `monitor profile` screenshot,
  [headless FS-UAE](headless-fsuae.md#harness-commands-native-builds)).
- **Put `SPRxPT` before a 256-colour AGA palette in the list**: the 24-bit palette is ~530
  MOVEs, about ten lines after the first WAIT at line 16, past the line-25 control-word fetch.
  Sprite data per display buffer, next to its list, avoids writing words DMA is reading.

## Dual playfield

- **PF1 is the odd planes (1/3/5), PF2 the even (2/4/6), and so are the modulos** (`BPL1MOD`,
  `BPL2MOD`). Two independent interleaved bitmaps, one per playfield, each need only their own
  modulo, and each layer keeps its own buffering: for example, double-buffered terrain on PF1
  and a single-buffered cockpit on PF2, rewriting only PF1's pointers at the swap.
- **PF2's pen 0 is transparent and PF1's is the background** (COLOR00), so PF1 has four colours
  and PF2 three. With two planes each, PF1 is COLOR00–03 and PF2 COLOR08–11; COLOR08 is never
  displayed. Count the colours in each region before deciding the split (remapping a source
  pen may be needed to fit PF2).
- `BPLCON2` bit 6 (`PF2PRI`, `$0040`) puts PF2 in front; it is inert without `DBLPF`.
- **A pen-level oracle cannot see a wrong colour register.** Read the copper back and check each
  PF2 register against its PF1 partner.

## Write-only registers

- **Every write-only display register (`BPLCON2`, …) is scene state with a named owner.** A list
  that does not write `$104` inherits whatever the previous scene left (a gauge drawn over the
  cockpit, but only after a scene change). Program sprite and playfield priority explicitly;
  never depend on the OS value.
- **`PFxP = 0` is playfield in front of every sprite**; `PFxP = N` is behind groups 0..N-1;
  `PFxP = 4` (`BPLCON2 = $0024`, what Intuition and the framework's `setPlayfield` write) is every
  sprite in front. It is easy to get both arms of an `#ifdef` inverted.
- **Never cache a write-only register's value**; one 16-bit store is cheaper than reasoning about
  who wrote it last.
- A 68000 read of `$DFF104` returns the floating bus; gdb's read under FS-UAE returns the stored
  value. Cross-check with `BPLCON0` (`$DFF100`). Use two marker functions rather than one with a
  tag argument: a breakpoint fires at entry, before the body records the tag.

## AGA display and palette

- **Reuse a proven mode and validate the words it writes.** A proven 320×200×8 mode: FMODE 3,
  interleaved 320-byte rows, `BPL1MOD`/`BPL2MOD` 280, `DIWSTRT` `$3881`, `DIWSTOP` `$00c1`,
  `DIWHIGH` `$2100`. The framework's AGA data-fetch branch is otherwise unverified.
- **`DIWHIGH` is always written, never inherited**; DIW is in lores, non-interlaced units.
- **Clear `BPLCON4` (`$10C`) on AGA**: an inherited bitplane XOR value remaps every pen
  (write 0 in the list).
- **Interleave the bitmap so chunky and planar share the row offset** (`y * 320`): one multiply
  serves both.
- **A 24-bit colour is two MOVEs**: high nibbles, then `BPLCON3` LOCT (`$0200`) low nibbles, with
  a bank switch every 32 colours; restore bank 0 with LOCT clear. A 256-colour load is ~528 MOVEs
  (a full list is about 558 longs). VGA 6-bit to 8-bit is `v << 2 | v >> 4`; a measured transfer
  table can replace a fitted gamma.
- **Record each colour MOVE's slot once and patch words in place** for palette changes; rebuild a
  list only after waiting for display blank, and apply queued palette changes at publication time
  (a mid-frame change splits one frame).
- Keep sprite palette setup from overwriting the 256 game colours.

## Chunky-to-planar, buffering and frame pacing

- **Full rows: Kalms `c2p1x1_8_c5_bm`** (width a multiple of 32, x a multiple of 8); it reads 32
  bytes past the source, so allocate +32. For dirty rows, call a row converter through a C ABI
  wrapper (the shared [Kalms adapter](../../share/kalms-c2p/README.md)). Record the pinned upstream revision.
- **Dirty rectangles**: 16-pixel aligned, merged on overlap, bounded; overflow unions, never
  drops. Combine a frame's bounds *before* C2P alignment, so separately aligned strips
  don't overlap. Compute bounds from what was drawn, never from shadow
  comparisons. For sparse updates a 16-pixel C2P that stores only final plane words and sparse pixels use per-pixel `BFINS`; 8-pixel and hybrid C2P gave no
  gain in one measured port.
- **Verify a C2P against a bit-level reference, hooking every destination store**, which catches
  intermediate values written to the shown bitmap. Keep the full-frame verifier out of
  speed measurements.
- **A double-buffered back buffer also converts the rectangles changed in the previous update**,
  or partial updates show two-frame-old pixels.
- **Single-buffered publication waits for the display-end edge** (line `$100`) as an edge, not a
  level; a late update publishes at once and missed slots are not queued (one port went from
  33–48 to 46–50 updates/s, no visible tearing).
- **Pace completed frames, never drawing calls**: one wait and one publication per completed
  frame.
- **Game time comes from a real-time clock in the original's units**, not a fixed credit per
  drawn frame, which runs slow motion when an update spans two frames. On fast CPUs cap
  source-defined animation loops at one step per field. See
  [fixed-time simulation](../playbooks/fixed-time-simulation.md).
- **Double buffering costs a second bitmap (64,000 bytes at 320×200×8) and every dirty region
  twice**: decide on measured headroom (~95 KB free was too little in one port).

## Blitter

- **The blitter is a measured candidate, not free.** On an A500 it shares the bus with the CPU: a
  whole-row blitter paint was byte-exact and 2× slower; only blits that replace CPU work (a
  D-only clear) paid [000]. On faster CPUs it can become the bottleneck.
- **Drain before CPU access**: CPU reads of blit targets wait, and CPU writes, cache eviction,
  free and teardown all need the blitter idle.
  Audit library calls as well as direct register writes: an asynchronous `BltClear` must
  finish before the CPU reuses its buffer. In one slave the clear raced LZW dictionary use on
  68040; waiting for completion fixed corruption with full MMU and CACHE enabled. Check
  this ownership boundary before attributing corruption to caches or disabling the MMU.
  Emulator success establishes that tested path, not real-hardware certification.
- **Interleaved bitmaps multiply blit height by the plane count**; split tall blits (a
  4-plane 292-row clear needs two).
- **The first/last-word masks apply to channel A only.** For a masked blit of a constant pen, put
  the opacity mask on A and the pen pattern on B; with opacity on B, unaligned edges stay
  unmasked. Cover the whole fetch span with the edge masks, including a zero mask for a spill
  word.

## Paula audio

- **Four DMA channels; allocate them by explicit priority rules** and document where the port
  departs from the original. Channels 0 and 3 are left, 1 and 2 right.
- **Period = 3546895 / Hz (PAL)**, clamp 124..65535; for higher rates use half- or quarter-rate
  loops prepared at load, with hysteresis.
- Convert samples once at load into Chip RAM as signed 8-bit with the original's gain. Volume is
  linear 0..64: map relative levels, not RMS.
- **Paula has no one-shot mode**: start the sample, and one VBI later point the reload registers
  at a two-byte silent loop; expire by VBI counters.
- **Keep DMA control in blanking**: stop in one VBI, program and start in the next. DMA control
  during display coincided with one-refresh horizontal strips in static scenery (20–40 ms
  latency). If a restart must wait inline, wait at least two sample periods of the largest
  period since the stop (from the Hardware Reference Manual's audio state machine). A
  channel stopped during its high byte finishes that period, then plays the low byte for one
  more period using the period register's current value (already the new note's, if the
  driver wrote it), and goes idle only then. Time the wait by the beam (count `VHPOSR` line
  changes, one line is about 227 colour clocks on PAL), never by CPU loops.
- **Protect note setup from the audio interrupt, not just DMA timing.** A pending request
  can consume a partially prepared attack/loop state before the new sample starts. Mask that
  channel during preparation and restore it only after the state and DMA startup are ready.
  The shared handler must intersect `INTREQR` with `INTENAR`: another channel can interrupt
  while the protected channel still has a pending request.
- **Check actual sample starts as well as acknowledgements.** In one slave's 68030 capture, an
  interrupt race replaced 19 initial 2,250-word sample lengths with 550-word loop lengths;
  the A500 reference did not. Compare note commands, driver state and DMA fetches. Account
  for the startup fetch discarded by Agnus, and verify actual capture lengths: a requested
  600-field Barto capture returned only 100 fields in this backend. Use bounded chunks and
  do not assume register continuity across their boundaries.
- **Or leave all DMA on and silence with volume 0**: period and volume changes are then plain
  pokes and only a waveform change restarts.
- `AUDxLEN` counts words; pointer and length latch only at a loop wrap. Odd loops need an aligned
  copy; no header bytes inside a loop. Clear the pending audio interrupt before writing `AUDxDAT`
  for direct output.
- **The LED filter is on at boot** (~5 kHz low-pass); turn it off when the original had none.
- **Re-host synthesised sound chips as chip state driving Paula loops**, not per-note rendered
  banks: square waves at computed periods; noise from a rendered LFSR or evolving buffers
  refreshed in slices. Envelopes clocked at 50 Hz quantise 100 Hz steps in pairs; a CIA
  timer fixes that. FM/OPL re-hosting is unexplored.
- Keep the refresh in the VBI and bounded in time, with no per-sample interrupt mixer.
  When the original drives more voices than it has channels, port its priority mixer and map
  its channels to Paula's, rather than mixing voices together (for example, 16 voice slots
  onto four POKEY channels).

## Input

- **Keyboard**: a CIA-A serial-port ICR handler via `AddICRVector`; if it returns the owner,
  remove theirs, add yours, restore on exit. Code = `ROR(~SDR, 1)`; the handshake holds SPMODE
  output ~85 µs. Clear modifier state at takeover: releases while the OS owned the keyboard never
  arrive.
- **Keep a level map and an edge latch.** A level poll misses taps shorter than its period (for
  example ~37 ms); latch the down edge, consume it when the original reads it, expire after a few fields.
  Never feed held keys only through an event queue. **Deliver a press until the original actually
  reads it**: a generated input clock edge is not acknowledgement (taps get lost that way).
- One raw-key → original-code table; count unmapped codes. Emulate typematic repeat if the
  original relies on it (for example 500 ms delay, 10.9/s).
- **Joystick**: `JOYxDAT` is crosswise quadrature (forward = b8^b9, left = b9, back = b0^b1,
  right = b1); fire is CIA-A PRA bit 7 (port 1) / bit 6 (port 0); button 2 is `POTINP` bit 14.
  Sample once per VBI. CD32 pads are a bit-banged read with interrupts off, detected over several
  spaced samples at boot.
- **Mouse**: left = CIA-A PRA bit 6; right/middle = `POTINP` bits 10/8 after `POTGO = 0`, or they
  read held on real hardware (FS-UAE does not model this). `JOY0DAT` counters are 8-bit and wrap:
  take the delta every frame and confirm the sign with a real mouse.
- WHDLoad OS switches can clear held-key state; see
  [WHDLoad MMU](../playbooks/whdload-mmu.md#compatibility-structures-must-have-real-backing-storage).

## Files, WHDLoad and the OS lifecycle

- **Load before takeover**; touch the disk only at explicit boundaries inside an I/O window
  ([OS takeover](#os-takeover-and-return)).
- **Whole-file reads in one `Read`; saves rewrite the file in place in one write**, skipped when
  unchanged (CRC); no temp file, backup or rename. Each WHDLoad OS switch is a visible pause plus
  write delay. Pre-create files that saves will overwrite: creating files under
  WHDLoad's write cache hung in low memory.
- **Use only the DOS packets WHDLoad's kickfs serves** (`Src/sources/whdload/kickfs.s`, the
  `.action` table). It has no `ACTION_RENAME_OBJECT`, `ACTION_CHANGE_MODE` (`ChangeMode`),
  `ACTION_SET_FILE_SIZE` (`SetFileSize`) or `ACTION_PARENT_FH` (`NameFromFH`, `ParentOfFH`).
  Without `DEBUG` its lookup does not stop at the table's end: an unknown packet jumps into
  code, a privilege violation or an Access Fault in the drive's task (`DH0`), the type in D4 of
  the dump (seen for rename, `ChangeMode`, `SetFileSize` and `NameFromFH`).
  `SET_DATE`, `SET_PROTECT` and `SET_COMMENT` succeed without effect. Instead: overwrite with
  `MODE_NEWFILE`, never rename; for a shared handle to a new or emptied file, `MODE_NEWFILE`,
  `Close`, `MODE_OLDFILE`; keep the opened path rather than asking the handle. Test every file
  write path under WHDLoad, not only native.
- **Handle Workbench startup yourself**: without `pr_CLI`, `WaitPort`/`GetMsg` the WBStartup
  before opening dos.library and reply last, under `Forbid`; the freestanding startup does
  neither. Last means after the finalizers (`fini_array`) too: once Workbench has the
  message back it may unload the code (RKM Libraries ch. 14). Data via `PROGDIR:`, identical
  under Shell, Workbench and the slave.
- **Parse Shell arguments with `ReadArgs`**, not by scanning `GetArgStr`: keywords are
  case-insensitive, `?` prompts with the template, a bad line fails with `PrintFault(IoErr())`
  and result 20. From Workbench read the icon's tool types with the same keywords. `ReadArgs`
  reads the line from `Input()`'s buffer: a WHDLoad slave must start the program with
  `RunCommand` (`SetArgStr` never reaches that buffer), and a supplied `RDA_Source` loses the
  `?` prompt on Kickstart 3.1.
- **List a directory in one `Examine`/`ExNext` pass; never rescan it per entry index.** An
  emulated DOS find-next that relocks and walks to entry N each call is quadratic: a 230-file
  drawer took 17 s with the drive light on. Snapshot the names once, match the pattern on names,
  then `Lock`+`Examine` only the matching files (838 to 5 fields in one measurement).
- The shared `_start` ignores `main`'s return value; supply a start that preserves it.
- **Flush caches after writing code at runtime** (`CacheClearU()` natively, `resload_FlushCache`
  under WHDLoad): see [hardware debugging](../playbooks/new-game-playbook-hardware.md#flush-after-the-final-executable-write).
- **WHDLoad's quit key cannot run deferred saves**, and must not be a game key (move it off
  F10 if the game uses F10).
- Crash dumps, installer updates and release archives: [native port validation](../native-port-validation.md).

## The shared framework

Ports vendor a C++ hardware framework; the canonical copy is `share/framework`
([framework](../../share/framework/README.md)). Vendored copies drift: check which copy a fix
came from before porting it, and compare a port's copy against the canonical one.

The framework's `setPlayfield` writes FMODE 3 on AGA with an unmeasured fetch window. A port
with its own display owner overrides it, with FMODE 0 or its own measured window.

- `--gc-sections` hides dormant link traps until the first caller; partial-link the framework
  (`ld -r`) to see them: a bridge with no asm body, a helper pulling `__mulsi3`, or methods
  declared (`getVBR`, `isLongFrame`, `isBlitterBusy`, `blitterWait`) without definitions in
  some copies.
- Non-interleaved asm arms of `Bitmap` were silent no-ops in older copies: treat interleaved
  as an invariant. Check that the factories free earlier allocations when a later one fails,
  and that `Bitmap` allocates the word-padded stride it draws at, not `width/8`.
- A statically allocated blitter queue leaks 49,158 bytes per launch unless released at
  shutdown.
- **Include every system header first and `AmigaHardware.h` last**: its bare register macros
  collide with `struct Custom` members.
- Record every local framework change in the project's `framework/` notes so it can be re-synced.

## Compiler traps in hardware code

- **`volatile` on every custom-chip pointer and interrupt-written flag**: `-O2` turned a
  blitter-queue wait into `bra.s .` and duplicated a `BLTSIZE` store.
  CIA registers too: through a non-volatile `ciaapraPointer` (older vendored framework copies)
  the 68020 build reads and tests `$BFE001` with `bfextu`, an access wider than the one CIA
  byte; volatile gives byte `move.b`s. Check a port's copy against `share/framework`.
- Normalise asm `Scc` results (`$FF`) with `!= 0` before using them as `bool`: `!b` gave `$FE`.
- No function-local statics: they need `__cxa_guard_*`, which the freestanding runtime lacks.
  Build with `-fcheck-new` so a failed `new` returns null.
- A cross-object `bsr` is `R_68K_PC16`, which `elf2hunk` cannot represent; use `jsr`.
- Every global a debugger reads must be kept from `--gc-sections` (a `PROBE_SYMS` list), or its
  symbol resolves into instruction bytes.
- 4-byte alignment of globals (`aligned(4)`), the mul/div audit and the other link audits: [port toolchain](port-toolchain.md)
  and [68k optimisation](m68k-optimisation.md#2-68000-versus-68020).
