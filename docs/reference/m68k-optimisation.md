# 68000/68020 code generation and optimisation

What ports have measured about making 68k code fast. Read it before optimising a hot function,
writing an assembly twin or writing a code generator. Numbers are tagged with the CPU they were
measured on: **[000]** a 7 MHz A500 (68000, no Fast RAM), **[020]** an A1200-class 68020;
untagged rules hold on both. Cycle figures do not transfer between them.

How to get a number you can trust and decide on it: [measurement method](measurement-method.md).
How to prove a faster twin still matches: [validation harness](validation-harness.md).
Compiler flags and link audits: [port toolchain](port-toolchain.md). Bus, DMA and chipset
costs: [Amiga hardware](amiga-hardware.md).

1. [Cost model](#1-cost-model)
2. [68000 versus 68020](#2-68000-versus-68020)
3. [Read what the compiler emitted](#3-read-what-the-compiler-emitted)
4. [Loops and memory access in C](#4-loops-and-memory-access-in-c)
5. [Inlining](#5-inlining)
6. [Registers](#6-registers)
7. [Arithmetic](#7-arithmetic)
8. [Hand-written assembly](#8-hand-written-assembly)
9. [Code generators and translators](#9-code-generators-and-translators)
10. [Work not done](#10-work-not-done)
11. [Size versus cycles](#11-size-versus-cycles)

## 1. Cost model

**The dominant cost is memory accesses and executed code, not arithmetic.** A literal,
instruction-for-instruction assembly rewrite of compiled C gained under 1%; the gains come from
executing less: inner loops that fit the cache, state in registers, hoisted invariants and
skipped work. A transliteration that keeps every original memory access (`mem[addr]` for each
6502 operand, a `volatile` shared with the interrupt handlers) is memory-bound before it does
anything else.

| Target | What it means | Measured |
|---|---|---|
| A500, 68000, no Fast RAM [000] | No caches: every instruction fetch and every load/store is a bus access. "Fast RAM" on an A500 is usually trapdoor slow RAM on the same bus. **Treat every access as equally expensive**; never justify a buffer as living in cheaper RAM. A zero-copy scheme beats any scheme that moves the data | Cycle-to-ms prediction needs a contention factor of ~1.6 (30 µs for a ~140-cycle loop at 7.09 MHz; then within 15%) |
| A1200, 68020, Chip RAM only [020] | 256-byte instruction cache, no data cache. A Chip access ≈ 7 CPU cycles, a cached instruction ≈ 2.5. Every longword fetched from outside the I-cache is a Chip access, so code volume costs | Compiled-C profiles are flat; per-object overhead adds up (32 stationary objects of ~1000 px were once ~30% of a frame's work) |
| 68020 with Fast RAM [020] | Fast RAM for code and data; Chip only for what DMA reads | Chip-destination writes cost 1.5× Fast-destination writes for the same C2P. Per-PC fit on FS-UAE: ≈ 1.09 cycles per code byte + 2.27 per data read + 3.07 per data write (R² 0.83); bytes inside cached loops are nearly free |

- With no Fast RAM every lookup table is a Chip read: a table must beat the ALU sequence it
  replaces (a velocity reciprocal table lost to `DIVS`).
- **Do not price code from published cycle tables.** Price by memory accesses and by code bytes
  fetched outside the cache, then measure. The 68000 tables are right for the instruction and
  wrong for the loop.
- Moving code shifts the cost of untouched instructions by up to ±0.7% on the 68020
  (branch-target alignment, cache placement). A gain smaller than that needs a matched
  repeat, not one run.
- The blitter shares the bus: it pays only when it **replaces** CPU work, not beside it
  ([Amiga hardware](amiga-hardware.md#blitter)).

## 2. 68000 versus 68020

| Topic | 68000 | 68020 |
|---|---|---|
| Instruction cache | None. Unrolled cold arms are never fetched: growing a routine from 282 to 785 instructions cost nothing | 256 bytes: the loop must fit. A 64-pixel C2P unroll regressed against the 32-pixel one |
| Data cache | None | None |
| Scaled index `(d8,An,Xn*4)` | Absent: shift, copy base, add per lookup | Present: scaled long index took 21.6% off a C2P kernel |
| Word index | — | `Xn.w` is sign-extended; addressing tables from their midpoint removed eight index clears per 32 pixels, −4.4% |
| Bitfields (`BFINS`, `BFEXTU`, `BFFFO`) | Absent; a table-emulated `bfffo` is expensive | Present; per-pixel `BFINS` into all planes suits sparse pixels |
| Word/long at an odd address | Address-error exception | Allowed, extra bus cycles |
| Longword at an address ≡ 2 mod 4 | No penalty | Extra bus cycle: 101 hot globals misaligned made a cold start ~8% and gameplay 0.65% slower. Fix with `alignas(4)` and a link audit |
| 32-bit `mul`/`div` | None. GCC calls `__mulsi3`, `__divsi3`, `__udivsi3`, `__modsi3`, `__umodsi3` (~200–600 cycles): ban them and audit every link | `mulu.l`/`divu.l`/`divs.l` exist. Direct constant division beat a reciprocal table |
| Shifts | 2n+8 cycles: `lsl.l #8` 24, `ror.w #8` 22. Byte swaps and pair builds are expensive | Barrel shifter: `ror.w #8` ≈ 1.8 cycles, about its two code bytes |
| Indexed displacement | `(d8,An,Xn)` only: a far table needs its own address register | Full-format EAs with 16/32-bit displacements |
| `movem` prologue | 10 registers ≈ 180 cycles, 3 ≈ 68: can exceed the whole win of an asm twin | Still scales with registers × memory accesses |

Measured 68020 probes on the FS-UAE model: indexed Fast word/long load 4.16/4.16 cycles;
immediate word/long store 6.22/8.28; `and.l #$ffff,dN` 6.1 against `tst.l` 2.1; high-byte
write by `ror`/`move.b`/`ror` 6.4 against `BFINS` 4.1; untaken short branch 1.3–1.4; immediate
word/long compare 4.0/6.4–6.6.

Standalone FS-UAE 68020/Fast probes (three 50-field runs) measure about three extra cycles when
a word/long crosses a four-byte boundary: word residue 3, long residues 1–3. Odd word residue 1
has no measured penalty. This applies to direct Fast accesses; do not transfer it to Chip RAM
or physical hardware. Long multiply/divide report only 4.12–4.14 cycles per PC, against about
21–22 for word multiply and 35–36 for word divide controls, in both cache-sized and oversized
loops. Treat those long costs as an emulator limitation, not a reason to prefer long arithmetic
on hardware. Record exact operands, binary hashes and loop sizes with such probes.

Some code must stay 68000-compatible while one routine wants 68020 modes: assemble only that
routine for the 68020. A game that is itself 68020 code needs no 68000 plan.

### Sharing optimized routines across 020/030/040/060

Audit instruction forms, not just mnemonic names. The 060 does not implement the
32-by-32 multiply form producing a 64-bit result in two registers; a routine that uses it
needs a division path there. Keep MOVE16 and other CPU-specific instructions behind
appropriate CPU checks. Distinguish a full FPU-equipped CPU from LC/EC parts, and test how
native replacements combine with FPSP patch lists. Unsupported FPU instructions must actually
trap in an emulator test intended to exercise FPSP; permissive emulation can hide the missing
native path.

Gate an optimization by measured benefit, not the CPU it was first developed on. A renderer
and Fast RAM placement can be shared across FPU-equipped CPUs while rotation caching pays only
on the full 040 and changed-block copying loses on the cacheless 020. Check each CPU
independently; a cache-dependent win need not help a CPU without a data cache. See
[measurement limits](measurement-method.md#compare-within-one-cpu-model).

## 3. Read what the compiler emitted

The source saying `move.l` guarantees nothing. **Disassemble before designing an asm twin and
after every edit to a hot function.** The tells:

| In the objdump | Means |
|---|---|
| `jsr <hot leaf>` where there were none, a new `.part.N` or `.constprop.N` symbol | An inlining decision flipped ([§5](#5-inlining)) |
| `n(sp)` operands on values that cannot change in the loop; pointers living in `Dn` and copied to `An` each iteration; a spill around an inner call | The register allocator ran out ([§6](#6-registers)) |
| A `bra` at the bottom of a loop and a `beq` out of the middle | GCC rotated the loop: ~8 cycles a unit of bookkeeping [000]. A conditional back edge (`bne.s`) is the good shape. You cannot ask for it; unroll to amortise it |
| A shift or multiply by a stride *after* a loop that had none | GCC reconstructs a pointer the exit test did not name ([§4](#4-loops-and-memory-access-in-c)) |
| `jsr memset` / `jsr memcpy` | A fill or copy loop was recognised as a library call; the freestanding versions are byte loops ([§4](#4-loops-and-memory-access-in-c)) |
| `__mulsi3` and friends | A 32-bit multiply or divide on a 68000 ([§7](#7-arithmetic)) |
| `ror.w #8` | A little-endian pair built with `|` ([§7](#7-arithmetic)) |
| `andi.l #255` and zero-extends around a loop index | The index is typed as a byte ([§4](#4-loops-and-memory-access-in-c)) |

- If GCC already inlined and unrolled a short loop, an asm twin must beat straight-line code and
  the headroom is small (a pointer-walked twin of a 12-slot scan was 5% slower than the
  unrolled C until it was unrolled as well).
- `.text` size is not the acceptance test: a change can shrink a function and make it slower,
  or improve one function and worsen the allocation of its neighbours. Diff per-function
  sizes and the instruction mix, then measure.

## 4. Loops and memory access in C

- **Locals, not memory, for loop scratch.** Hoist running pointers, counters and invariants that
  the original kept in zero page into locals; write back only the final value the oracle checks.
  Intermediate stores that the next iteration overwrites are dead.
- **Walk pointers with post-increment; never multiply-and-index per step.** Deriving an address
  from a cell index each step (shift, `lea`, mask) cost 76% of one walk; a stride multiply in an
  address emitted `__mulsi3`.
- **But a pointer loop does not beat an unrolled absolute scan.** Over a short fixed array GCC
  may emit straight-line `move.b abs.l` + `beq.s` (26 cycles/element) against a pointer loop's
  36: loop bookkeeping exceeds what autoincrement saves [000].
- **Loops over three or more pointers**: GCC's ivopts turn N pointers into one index plus N
  bases, so every access becomes `(0,An,Dn.L)`, 14 cycles of EA for a long against 8 for
  `(An)+`. The fix, all three parts measured:
  1. Exit on a **pointer compare against a precomputed end** (`do { … } while (p != end);`),
     not a counter: 170 → 121 cycles/long.
  2. **Post-increment every pointer**; one `*p` with a separate add cost 16 cycles/long.
  3. Remove the counter for constant trip counts by unrolling: 70 → 46.
- **Test the pointer whose final value is still wanted after the loop.** GCC makes the pointer
  the exit test names the induction variable and reconstructs the other; if code after the loop
  needs the other one, that is a spill, a shift and an add per run (~70 cycles a run).
- **Byte-typed indices and `volatile` round trips blind loop analysis.** A `uint8_t` counter
  (because the 6502 held it in a register) pays a mask and a zero-extend on every use and hides
  the stride; a `volatile` save across a call is an opaque write. Removing both turned an
  unanalysable loop into a ×3 unroll with one exit test (loop tail 22 → 6 cycles a pair). Fix
  these before anything cleverer.
- **Unroll for constant displacements.** Four units a turn took a byte-load/test/store loop from
  64 to 43 cycles/unit [000]: three of four units use `d16(An)` (4 cycles) instead of a pointer
  bump (8), and one back edge serves four. Choose the factor from the run-length distribution
  (runs averaging ~17.7 units: ×4, not ×8). On the 68020 the limit is the I-cache.
- **`#pragma GCC unroll` is not reliable**: it removed the bookkeeping in some loops at `-O3`
  (where `-O3` did not unroll an 8-trip loop unasked) and was ignored in another at `-O2`
  (byte-identical output). Check the output; hand-unroll with a file-scope macro when it
  matters.
- **Batch sequential bytes into `move.l`.** The win is the batching, not dropping `volatile`: for
  scattered byte access a non-volatile alias is a measured no-op. A `move.l` needs an even
  address on the 68000 (4-aligned only for 68020 speed). "Odd offset" is not "odd address", and
  abutting runs merge into one fill.
- **GCC can undo the batching**: a plain `uint32_t *` fill loop becomes `jsr memset`, and the
  freestanding `memset`/`memcpy`/`memmove` are byte loops (~24/28/~40 cycles a byte [000]).
  Build with `-fno-tree-loop-distribute-patterns`, replace the library routines, or keep the
  pointer `volatile`. `volatile` is not free either: two interleaved volatile long pointers made
  GCC emit a redundant read before every store.
- **Never alias little-endian guest memory through wide pointers.** A big-endian 68k reads a
  byte-swapped value, and a little-endian host validation passes while the Amiga renders garbage.
  The one safe case is a uniform-byte broadcast (all four bytes equal). Lint for it.
- **Split a fused loop** that carries pointers only its rare path needs, or that both finds and
  acts: two passes over a small stack array each fit in registers (128 → ~80 cycles).
- **A call boundary is an aliasing barrier**: an inline sequence of 67 cycles cost ~2700 through
  a `jsr`. State reachable through an escaping pointer is reloaded every iteration; pass values
  in and a packed result out, or sync locals only around the cold call.
- Longword strided copies with unrolled `move.l` (eight per 32 bytes) ran 2.366× the C path;
  interleaving lookups between plane writes lost unless it also removed instructions [020].
- Mark `volatile` only what an interrupt really races.

## 5. Inlining

Specialised hot routines are fast *because* they are inlined, and GCC's size heuristic can
revoke that silently. **When a size-changing edit regresses, count the `jsr`s to the hot leaves
before reasoning about register pressure**; a register-pressure diagnosis made without counting
has had to be retracted.

| Case | What happened | Rule |
|---|---|---|
| A body got smaller | Replacing two table scans with `switch` saved ~300 cycles per span and measured −0.6%: the body fell under the inlining threshold and four specialisations became one shared out-of-line copy taking a pointer again. With `always_inline`: +0.8% | Pin `always_inline` on a routine that is fast because it is specialised |
| A body inlined twice | One source body serving two compile-time configurations doubled its host and pushed the hot leaf out of line: 17.13 → 21.46 ms/frame. Cold instance in its own `noinline` wrapper plus `always_inline` on the leaf: 10.40 ms. A second expansion of a plot macro at one site added ~750 bytes and outlined the whole function into `.part.0` | Keep one expansion; pass the difference as a runtime parameter or move the cold copy out |
| A short list with an explicit count | GCC peels and unrolls by the declared bound: four unrolled loops over a usually one-entry list made a 348-instruction body that missed inlining at 25 call sites. Terminating on a sentinel: 108 instructions, −0.8 ms/frame | Before reaching for an attribute, ask what made the body big; terminate short lists positionally |
| A shared `always_inline` leaf grew | Six instructions in a leaf inlined into the universal store choke point became 104 copies in 14 functions; an unrelated loop lost its unroll. `--param inline-unit-growth` changed nothing and splitting the TU cannot help | Count a leaf's call sites before growing it. Diagnose by diffing per-function sizes between two objdumps and intersecting with the leaf's callers. Mark at the few producer sites instead of hooking every store |

- `always_inline` on a leaf does not fold a descriptor whose *selection* is a runtime value;
  specialise the selection too (two `noinline` twins, one per descriptor, for a large leaf).
- The constant-parameter rule holds for a leaf in an inner loop, not for a caller already at the
  register ceiling: inlining a routine whose arguments were literals at every site still cost
  +1.04 ms/frame because the caller grew 757 → 995 instructions.
- A test that is invariant across an inner loop belongs in a specialisation: classify once,
  dispatch to `always_inline` variants.
- `__builtin_expect` on the condition, spelled as the mismatch (`if (__builtin_expect(a != b,
  0))`), keeps the common case falling through; written as `if (clean) continue;` it routed the
  common case through two taken branches (~8% of the loop).

## 6. Registers

The 68000 has eight address registers, and a GCC function that saves `d2-d7/a2-a6` has used all
eleven callee-saved ones.

- **A hoisted base pointer is a second representation.** If every input of a hoisted value is
  already live, hoisting buys an add and sells a register; the spill shows up elsewhere. Forming
  both pointers at the point of use took stack operands 21 → 12 and the function got smaller.
  When the allocator is saturated, the question is whether to hoist at all, not which.
- `(d8,An,Dn.l)` has an 8-bit displacement, so a base with a large constant cannot be re-formed
  by an addressing mode. GCC reassociates through parentheses, so you cannot spell your way to a
  constant base register.
- **Spell byte operations in byte width.** `(x - 1) & 0xFF` on an `unsigned` made GCC
  materialise the mask and spill a live value; `(unsigned char)(x - 1u)` is `subq.b`, the same
  value for every input. The tell is a stack slot next to arithmetic that needs none.
- **Pack registers only where one pack serves many reloads**: the 68000 has no byte insert, so
  packing and unpacking three bytes costs ≈ 40 cycles [000] (`BFINS` on the 68020).
- When a callee uses all fifteen registers, state crossing the call has nowhere cheaper than its
  own memory cell.

## 7. Arithmetic

- **Signed shifts encode a rounding policy.** `ASR #2` maps −1 through −3 to −1,
  while +1 through +3 become zero, so a steering or bank calculation built on it biases
  small corrections to one side. Where symmetric truncation toward zero is intended, add 3 to
  negative operands before shifting by two; preserve operand width and check the range.
  This changes native behavior, so treat it as an approved handling correction rather
  than a bit-exact optimisation. Check paired positive/negative small inputs and reversals;
  preserve the original rounding when native equivalence is the requirement.
- **Never emit a 32-bit software multiply or divide on a 68000.** The 68000 has only
  `MULU.W`/`MULS.W` (16×16→32) and `DIVU.W`/`DIVS.W` (32÷16→16q:16r). Keep a header of
  inline-asm 16-bit helpers (plain C on the host) and an objdump audit that fails the link on
  `__(u?div|u?mod|mul)si3`; the audits are in [port toolchain](port-toolchain.md). Check the
  operand ranges before using a helper.
- When a value looks 32-bit: fold constant factors with `⌊n/(ab)⌋ = ⌊⌊n/a⌋/b⌋`; reduce with
  `(ab) mod m = ((a mod m)(b mod m)) mod m`; replace a small-modulus wrap with compare-subtract;
  clamp an input so `2x` stays below 2¹⁶.
- **Exactness first**: a sign-magnitude multiply is `mulu.w` plus a conditional `neg`, not
  `muls.w` plus `asr` (off by one); some "multiplies" in the original are tables, not products.
- A divide becomes a table only when the table wins on that target ([000]: a 512-byte table
  replaced `divu` + `divs` ≈ 300 cycles; [020]: a reciprocal table lost to `DIVS`).
- **Build a little-endian pair as `lo + 256*hi`, never `(hi << 8) | lo`.** `or.b` reaches only
  bits 0–7, so GCC builds the big-endian word and byte-swaps it back: 74 cycles, 46 of them
  shifting [000]. `+ 256*hi` is identical for byte operands and costs 58; two pairs added
  factor into one shift (152 → 98). Flipping operands, `__builtin_bswap16` and splitting into
  locals all canonicalise to the slow form. Write new pair loads this way from the start; a
  sweep over existing sites cost more instructions than it saved in most functions.
- The high byte of a word without a shift [000]: `move.w d,-(sp)` / `move.b (sp)+,x` is 24
  cycles against 38 for `lsr.w #8`. Re-measure on the 68020, which has a barrel shifter.
- A big-endian copy of a guest word keeps its low byte at offset +1.

## 8. Hand-written assembly

Escalate to assembly only after the idiomatic C is clean and still hot: GCC won't keep `(a0)+`
across three pointers, has no scaled index on the 68000 and spills under pressure. A hand
rasteriser beat the C by ~27% where four C restructurings had regressed. Every routine needs an
in-process differential against its C version ([validation harness](validation-harness.md)).

- **GNU as for new routines**: `m68k-amiga-elf-as --register-prefix-optional` takes Motorola
  syntax and gives `.macro` with `\name\()_suffix` pasting, `.type`/`.size` (so addr2line and the
  PC sampler name the routine) and **`.subsection 1` for cold arms**, which lands them after the
  routine so the hot path falls through. Put the `.size` end label in subsection 1, or use a
  `.L` end label: a plain end symbol has the next function's address and names it.
- **vasm with `-no-opt`** keeps hand encodings exactly as written, so hot in-range branches must
  be marked `.s` by hand; rename dot-in-middle labels, which vasm reads as local.
- **Leave branch sizes to GAS** (`jbne`, unsized `bne`) in a routine that will grow: a short
  branch that stops reaching is an error, and `bcc.s` to the very next instruction is illegal.
  A sabotage that deletes the instruction a short branch skips must leave a same-size no-op.
- **`|` is the comment character**: `andi.l #A|B,d2` silently truncates. Name constants with
  `.equ`. **Parenthesise macro arguments in expressions** (`\y*ROWB` with `y=2*0+1` put every
  odd line on the wrong row; only the oracle's self-test pages caught it).
- **Bridge from C with pinned register variables** (`register uint32_t x __asm("d5")`, `"+d"`/
  `"+a"` for every changed register, `"memory"` clobber), and have the routine save only a5/a6
  (either may be GCC's frame pointer). When the bridge would run per call, move the loop into the
  asm and make it a C-callable function instead.
- **The GCC ABI at runtime exits**: callees clobber d0/d1/a0/a1; arguments are pushed as longs,
  right to left. An oracle checks the stack, callee-saved registers and the return path.
- **Unroll to make operands constant**: twelve unrolled routines were ~9 KB, free on a cache-less
  CPU. A far table needs its own address register, stepped with the index (wrap-exact for a
  byte index).
- **Dispatch**: a PC-relative `jmp tab(pc,d.w)` of `bra.w` entries (the table right after the
  dispatch, within the 8-bit displacement) beat a compare chain, 36 cycles flat against 49.5
  weighted. A 256-byte decode table with `$FF` as "cannot mean" beats a compare chain for a
  byte with ~17 legal values. `pea (a5,d7.w)` / `rts` enters a computed address without
  spending a register on the table base. A dispatch must not modify the value it dispatches
  on. A computed entry into an unrolled body (`move.l (a0)+,d0` / `beq.s` ×20) serves
  variable-length scans.
- **Specialise per colour, not per pixel rule**: with one foreground on black a plane is the glyph
  or zero, so eight unrolled routines made a glyph line one fetch and three stores. Any even
  address takes a longword on the 68000.

ISA traps that assemble cleanly and disassemble to exactly what you meant, so only running on
the target finds them:

- **`ROR`/`ROL` do not touch X; `MOVEQ` does not write X.** `ABCD`/`SBCD`/`ADDX`/`SUBX`/`NEGX`
  take their carry from X. Seed X with `lsr.b #1` on a 0/1 byte; read it with `moveq #0` +
  `addx.b`. A wrong form passed review; an on-target sweep found 4500 failures in 40000.
  **Inline asm is unverified until it has run on the target.**
- **`MOVE` sets N/Z; `EXG` sets no flags**: `tst / exg / bmi` works, `tst / move / bmi` does not.
- A patched or replaced routine preserves every live register and **all five CCR bits including
  X** (for example a copy kernel's final N/Z and X).
- **Avoid privileged SR reads in 020+ condition-code wrappers.** In user mode,
  `MOVE.W SR` traps on 68010 and later; WHDLoad can emulate it at substantial cost
  (privilege-emulated SR reads have consumed about a quarter of a game update).
  If the contract needs only condition flags, use `MOVE.W CCR` on 020+ and restore the
  CCR without changing supervisor or interrupt state. Preserve all five flags, including X,
  and validate the wrapper against the original. Keep a separate 68000 path: it has no
  `MOVE from CCR` instruction, while its `MOVE from SR` is unprivileged.
- **Audit every address's width, then its value range.** A `.w` address sign-extends above
  `$7FFF` and writes somewhere else. What finds such a wild write is a hardware watchpoint
  (prove it fires on a known write first), a checksum canary over the damaged area, and a
  lookup from runtime address to symbol.

## 9. Code generators and translators

For static recompilers and transpilers, on top of everything above:

- **Keep guest registers resident across blocks; materialise full guest state only at a proven
  boundary**; no CPU structure in translated regions. Direct guest edges become direct native
  edges.
- **One base register for guest RAM**: `abs.l` operands become `d16(An)`, 16 → 12 cycles, 6 → 4
  bytes and one fewer HUNK `RELOC32` per operand (20 folds saved 14,352 bytes in one
  executable). A base at `mem+$628F` reaches every cell below `$E28E`. For a segmented guest, a
  base at segment+`$8000` puts a whole 64 KiB segment in `d16` range.
- **Flags stay virtual**: compute a flag only when a reader is live, reuse the CCR where the
  semantics agree, and replay only flags that escape. Removing push/pop-flags memory traffic gave
  +5.9% frames per second. Reuse an instruction's own flags (V from `add.w`).
- **Guest RAM stays byte-exact; every native word/long access states its endian and alignment
  rule.** Keep wide guest values in registers in native order and convert only at the memory
  boundary. A byte-reversed guest layout (guest byte L at host TOP − L) makes a little-endian
  guest word a native big-endian word one byte lower; with biased segment bases, SP/BP mirror
  as offset ^ 7FFFh, and upper register words can be left undefined. Fix the contract before
  mass generation: a late layout change re-plumbs the harness.
- **Make store targets statically known**: a store to a constant RAM address needs no device or
  bus check (removing an unreachable range test saved 1.17 ms a frame).
- A translator change changes the oracle too: record baselines before changing the CPU model or
  memory representation ([validation harness](validation-harness.md)).

## 10. Work not done

The largest wins were work skipped, not faster loops.

- **Read what the worst case is made of before tightening its loop.** A page that was 421 blank
  pairs of 500 went from 47 to 34 ms by skipping the decoder and painter for blank rows with one
  blitter clear; the asm had taken it from 64 to 47.
- **Divide by the right denominator**: a loop that looked like 3500 cycles per scan line was 43
  spans with the weight in per-span setup. Count how often a loop runs first.
- **Skip unchanged work** with per-writer dirty flags or dirty ranges keyed on inputs.
  Shadow-compare scans are themselves full scans, a 68000 no-go. Narrowing a dirty signal needs a
  survey of every reader.
- **A check-before-doing scheme re-reads the byte the check avoids**: it recovers only the
  bookkeeping.
- Retention schemes can cost more bookkeeping than the redraws they save (point and sprite
  retention and area-aware dirty merging have all measured slower). Price them like any other
  change ([measurement method](measurement-method.md)).

For an already coalesced arena, resizing one allocation can create adjacent free
blocks only at its newly split tail. `HeapResize.inc` merges that pair locally;
it preserves placement and accounting without walking unrelated blocks. Consumers
must test the no-adjacent-free-block invariant alongside fragmented grow/shrink,
compaction, payload, flag and failure checks.

## 11. Size versus cycles

A fold that turns `abs.l` operands into `d16(An)` has two acceptance tests that can disagree:

- **For cycles**, the test is the function's own `.text` and timing in a whole-TU diff; a fold
  that spills or grows two inline sites loses.
- **For bytes**, the test is the final hunk, where relocations usually dominate: one 956-operand
  boot routine grew its `.text` by 794 bytes yet shrank the executable by ~1.6 KB (−299
  relocations). Keep such folds in boot and bulk code, where cycles do not matter.
- Read a function and its `.part.N` siblings as one when comparing sizes.
- Count `RELOC32` entries in the hunk, not the ELF: `elf2hunk` adds them.

## Overlap-safe longword copies

`share/mac-runtime/BlockMoveBytes.h` is a 68020+ copy helper. It selects traversal direction
for overlapping ranges, aligns the source, uses longword transfers and retains byte tails. The
bulk loop is 128 bytes; small copies never enter it. `BlockMoveChecks.h` supplies 28,388
independent byte-oracle cases, including every alignment, short overlap and large loop
boundaries. Run `make test-block-move` for the sanitizer host gate. Consumers must also run the
fixture on their target and measure their own workload; 68030 evidence is not a 68020 timing
claim.
