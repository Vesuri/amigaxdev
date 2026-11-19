# x86 real mode for translators and oracles

Facts a DOS port's decoder, IR, 68020 lowering and oracles must get right, and the
deviations of the oracles themselves. Rows marked **[checked]** were settled by an
instruction differential against Unicorn and, where Unicorn deviates, live DOSBox-X;
everything else is architecture knowledge (Intel and Motorola manuals) that needs a
differential case before a lowering relies on it. The method is in the playbook's
["x86 translated or recovered"](../playbooks/new-port-playbook.md#x86-translated-or-recovered);
the reference emulator in [the DOS reference](dos-reference.md); the runtime's services, EMS,
overlays and interrupt delivery in [the runtime under translated DOS code](dos-runtime.md).

## The CPU mode decides the contract

Settle the instruction set from the executed images before choosing the register and
memory contract:

- **Census the opcodes** by byte-pattern frequency against chance, over code reached by
  recursive descent and the trace, never a linear sweep: 80186 forms (`push imm` 68h/6Ah,
  `imul r,r/m,imm` 69h/6Bh, shifts by an immediate C0h/C1h, `enter`/`leave` C8h/C9h,
  `pusha`/`popa`, `bound`, `ins`/`outs`), 286 protected-mode forms, and 386 forms
  (operand- and address-size prefixes 66h/67h, 0Fh two-byte opcodes, FS/GS, 32-bit
  addressing), FPU escapes, `WAIT` and `LOCK`.
- A 16-bit real-mode contract (guest registers in 68k data registers with **upper words
  undefined**, segment bases recomputed on segment writes) holds for 8086 and 80186 code.
  32-bit registers or a DOS extender (protected mode, flat 32-bit segments) break it and
  change the translator, not only its decoder.
- **A "16-bit" program can still run 386 code**: a runtime library can probe the CPU and take
  an optional 386 path (operand-size prefixes, `pushad`, `pushfd`, FS/GS). The classic
  probe is PUSHF: on a 286 in real mode bits 12–15 read 0, on an 8086 1, and a 386 can set
  12–14. Find the probe and decide which path the port takes; the reference must take the
  same one.
- **A linear sweep invents instructions from ASCII**: one overlay's sweep gave 126 `outsw`,
  105 `outsb`, 104 `insb`, 42 `bound` and 30 `daa`. Count only code reached from proved
  entries.

## Flags and the 68k CCR

FLAGS: CF 0, PF 2, AF 4, ZF 6, SF 7, TF 8, IF 9, DF 10, OF 11.

| Topic | x86 | 68k | Lowering |
|---|---|---|---|
| Carry on SUB, CMP, SBB, NEG | CF = borrow | C = borrow (X too) | same convention |
| CMP operand order | `cmp a,b` = a − b | `cmp src,Dn` = Dn − src | swap operands |
| Branches | JB JAE JBE JA / JL JGE JLE JG / JS JO | BCS BCC BLS BHI / BLT BGE BLE BGT / BMI BVS | direct when the producer is ADD/SUB/CMP |
| MOV, LEA, XCHG, CBW, CWD, PUSH, POP | no flags | `MOVE`/`CLR`/`EXT` write N Z and clear V C; `MOVEA`, `LEA`, `EXG`, `MOVEM` do not | data moves clobber the CCR: schedule flag consumers first or rematerialise |
| INC, DEC | OF SF ZF AF PF; **CF kept** | `ADDQ`/`SUBQ` to Dn write C and X; to An nothing | preserve CF when live |
| AND, OR, XOR, TEST | CF = OF = 0, SF ZF PF, AF undefined | V = C = 0, N Z | match except PF |
| ADC, SBB | ZF from the result | `ADDX`/`SUBX` use X; Z only cleared | set X from CF first; seed Z or test separately |
| NEG | CF = (src ≠ 0) | C = X = (result ≠ 0) | same |
| MUL, IMUL | CF = OF = high half significant; SF ZF AF PF undefined | `MULU`/`MULS` N Z, V = C = 0 | compute CF/OF only when live |
| DIV, IDIV | flags undefined; quotient AX, remainder DX; overflow or /0 → INT 0 with IP at the DIV (286+) | `DIVU`/`DIVS.W`: quotient low word, remainder high; /0 → vector 5; overflow sets V, no trap | swap halves; overflow raises the guest's INT 0 |
| AF, PF | nibble carry; even parity of the low byte | none | lazy: needed by DAA DAS AAA AAS, LAHF, PUSHF, JP JNP |
| LAHF, SAHF, PUSHF, POPF | expose the flags | — | a full materialisation boundary; build it only where observed |
| LOOP, JCXZ | no flags | `SUBQ` clobbers the CCR; `DBcc` does not | `DBcc` with a biased counter, or virtual flags |

## Shifts and rotates

- 80186 and later mask the count to 5 bits; the 8086 does not. A count of 0 after masking
  changes no flags. 68k register counts are mod 64; count 0 clears C (X unchanged);
  `ROXL`/`ROXR` count 0 sets C = X.
- SHL/SAL: CF = the last bit out; OF only for count 1 (MSB of the result xor CF). 68k `ASL`
  sets V if the MSB changed at any step; `LSL` clears V. Lower SHL as `LSL` and derive OF
  only when live and the count is 1. SHR count 1: OF = the original MSB; SAR count 1: OF = 0.
- A count at or above the operand width (possible after masking a 16-bit operand): CF and OF
  are undefined. Mask in the oracle, reproduce the result bits.
- ROL/ROR change only CF and OF; 68k `ROL`/`ROR` write N Z and clear V. RCL/RCR rotate
  through CF, with a 16-bit count masked to 5 bits then taken mod 17; 68k `ROXL`/`ROXR`
  rotate through X: set X from CF first.

## Segments and addresses

- Physical = segment × 16 + offset. Effective-address offsets wrap at 64 KiB
  (`[bx+si+disp]`, SI and DI in string operations, SP), and game code relies on it (plane
  offsets, screen-transition sources).
- Default segments: BP-based → SS, others → DS, string destination ES:DI (not
  overridable), the stack SS:SP. `MOV SS` and `POP SS` inhibit interrupts for one
  instruction.
- **[checked]** A word access at offset FFFFh touches linear `base+FFFFh` and `base+10000h`
  (no wrap inside the word, no fault), as DOSBox does. With A20 on, `FFFF:0010` is linear
  100000h.
- **[checked]** LES/LDS take the segment word at offset+2 mod 64 KiB (the offset word does
  not wrap). Far `call`/`jmp [m]` read the segment word linearly at `base+offset+2`.
- **[checked]** `push sp` stores SP before the decrement; `pop sp` loads the popped word.
- **[checked]** IDIV accepts the most negative quotient (−128, −32768). DIV/IDIV overflow,
  divide by zero and `aam 0` fault with IP at the instruction and the registers unchanged.
- **[checked]** POPF in real mode keeps FLAGS bits 12–14 (386) and clears 15.
- Callers can pass bytes as words and callees use only the low byte: never assume a zero
  high byte.

## String instructions

- DF = 0 increments, DF = 1 decrements; treat DF as a live guest flag and specialise only
  where analysis proves it. `rep` with CX = 0 runs no iteration and changes no flags.
- REPE/REPNE with CMPS/SCAS stop on ZF; the flags are those of the last comparison.
- Overlap is defined per element, forwards: `rep movsb` with DI = SI + 1 replicates a byte.
  Never lower to `memmove`. SI and DI wrap at 64 KiB independently mid-string.

## Calls, returns and compiler idioms

- A near CALL pushes IP; a far CALL pushes CS then IP; `retf n` pops IP and CS, then adds n.
  `push cs; call near` calls a far routine in the same segment (treat it as a far call);
  `push seg; push off; retf` is a far jump.
- Code can pop or rewrite its return address (inline parameters, dispatch, an overlay
  manager redirecting returns): the reason for the runtime's
  [return-site check](dos-runtime.md#calls-and-returns).
- Microsoft C/LINK far code uses a frame paragraph up to 15 bytes below a function's first
  byte, inside the previous function: CS follows control flow, not address. Take a far
  function's CS as its entry rounded down to a paragraph.
- Runtime helpers for long arithmetic pop their own arguments (`retf 4/6/8`) where game code
  leaves cleanup to the caller. Name the C runtime's routines by instruction-shape
  signature against a pinned binary of the same compiler.
- Handlers installed with `mov dx,imm` then INT 21h AX=25xxh, and continuations pushed as
  return addresses (`mov bx,imm; push bx`), are entry points that static descent cannot see.

## Interrupts, ports and video

- IVT at `0000:0000`, four bytes a vector. `int n` pushes FLAGS, CS, IP and clears IF and
  TF. Master PIC IRQ0–7 → INT 08h–0Fh; BIOS INT 08h increments the tick count at
  `0040:006C` and calls INT 1Ch. Games also read IVT bytes as data.
- A timer handler runs from game code and during DOS services: it is asynchronous state,
  not a call ([playbook §7](../playbooks/new-port-playbook.md#rules-for-any-generator-or-translator-transpiled-6502-translated-x86)).
  A handler that reaches STI before its EOI can be re-entered by a tick posted meanwhile.
- Ports: PIC 20h/21h (`out 20h,20h` is EOI); PIT 40h–43h (1,193,182 Hz input, latch then
  read low and high from 40h); keyboard 60h/61h (set-1 codes, break = make | 80h, `E0`
  prefix); joystick 201h; VGA 3C0h attribute (flip-flop reset by reading 3DAh), 3C4h/3C5h
  sequencer (02h map mask, 04h memory mode), 3C7h–3C9h DAC (6-bit, auto-increment),
  3CEh/3CFh graphics controller, 3D4h/3D5h CRTC (0Ch/0Dh start address), 3DAh status
  (bit 3 vertical retrace); AdLib OPL 388h/389h; Sound Blaster at its base (220h).
- Delay loops latch the PIT, and frame waits spin on 3DAh, millions of times: a host run
  replays those reads as recorded streams, and the target answers them from a model.
- Mode 13h (`int 10h AX=0013h`): 320×200, chain-4, linear at `A000:0000`, pixel at
  y × 320 + x. Clearing chain-4 and setting CRTC 14h/17h gives an unchained planar layout
  (four planes, several pages) whose inner loops program the sequencer and graphics
  controller: treat it as its own display model.

## MZ executables

- Header: `+02` bytes in the last page, `+04` 512-byte pages, `+06` relocation count, `+08`
  header paragraphs, `+0A/+0C` min/max alloc, `+0E/+10` SS/SP, `+14/+16` IP/CS, `+18` the
  relocation table, `+1A` overlay number. `python3 -m amigaxdev.dos.mz_info` reads it and
  detects Compack.
- The image loads at PSP + 10h; each relocation adds the load segment to a word. Entry
  DS = ES = PSP. Normalise traces by subtracting the load segment.
- The relocation table marks segment-valued words: a free classifier for far pointers and
  segment immediates, though not every segment value is relocated (computed, overlay or
  PSP-relative segments).
- A packed executable (Compack, LZEXE, a publisher's own container) is not trusted until its
  unpacked image and entry state have been captured from the reference and reproduced from
  the file ([playbook §3](../playbooks/new-port-playbook.md#3-extract-the-original-data)).

## Unicorn x86-16 as an oracle

Unicorn 2.1.4 (`$AMIGA_UNICORN`) deviates in these ways; each was probed on the host:

| Quirk | Handling |
|---|---|
| `uc_mem_write` does not invalidate translated blocks | flush (`UC_CTL_TB_FLUSH`) after every patch |
| `count=1` runs one REP iteration | stop from a code hook at the next instruction boundary |
| An interrupt hook skips QEMU's delivery: the next exception becomes a double fault, then a silent triple fault | reopen the engine after every exception |
| A REP string right after a flag setter in one translation block recomputes OF/AF wrongly (`add cx,3636h; rep movsb` clears OF) | one instruction per `uc_emu_start` |
| `retf` at SP ≥ FFFDh reads CS without the 16-bit wrap; LES/LDS at FFFEh/FFFFh read the segment word unwrapped | execute those cases in live DOSBox-X (heavy-debug single step), comparing registers, flags and the 1 MiB window |
| A self-overwriting REP refetches the modified instruction | discard the case |
| A store into the 4 KiB page of the executing instruction restarts it; stopped after one instruction it has not run | count as an oracle deviation when IP did not move |
| A software `int n` on an exception vector (0, 1, 5, 6, 8, 13) goes through QEMU's exception path | count as an oracle deviation, never compare |
| A `count` given to `uc_emu_start` hooks every instruction (one host run: 291 s instead of 43 s) | stop long runs on a timeout instead |
| Capstone prints `notrack` for 3Eh-prefixed call/jmp, and `cdq`/`cwde` for CWD/CBW in 16-bit mode | normalise in the decoder cross-check |

Unicorn's 68020 and the interrupt-hook service layer: [port toolchain](port-toolchain.md#analysis-tools).
