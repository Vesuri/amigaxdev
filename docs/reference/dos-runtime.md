# The runtime under translated DOS code

What the hand-written runtime of a translated DOS program models, and the contracts that
held. The translator's method and guardrails are in the playbook's
["x86 translated or recovered"](../playbooks/new-port-playbook.md#x86-translated-or-recovered);
the original running as the reference in [the DOS reference](dos-reference.md); instruction
semantics, MZ executables and the oracles' quirks in [x86 real mode](x86-real-mode.md).

## Services

- **Answer every service as the reference emulator does**: EMS allocation order and page
  counts, MCBs and the PSP, INT 33h, the BIOS keyboard buffer. Guest RAM then compares with
  the reference directly. The reference's `svc`/`svc_ret` records are the oracle
  ([the patch set](dos-reference.md#the-patch-set)).
- Load the user's original executable into guest RAM at run time, so the shipped program
  holds only translated code.
- INT 33h takes the reference's mickey ratios, not a real mouse's
  ([input](dos-reference.md#input)).

## Calls and returns

- Guest calls become `jsr`/`rts` over a byte-exact guest stack, with the popped CS:IP checked
  at every return site. A mismatch (an overlay manager rewrote the frame, code popped its own
  return) re-dispatches far or stops by name. Where guest code does that:
  [x86 real mode](x86-real-mode.md#calls-returns-and-compiler-idioms).

## Memory: EMS and XMS

- **EMS mapping must cost what it costs on a PC**: a page-table change, not a copy. Copying
  two 16 KB pages byte by byte per map can take a quarter of a scene's cycles. Design the EMS
  model for speed before the first profile: map pages lazily, run guarded ES accesses on the
  store page itself, and copy in only at DS/SS loads of the frame (one port cut its copies to
  one milestone from 82 MB to 5.7 MB). A page mapped at two frame pages is one memory. At
  least use long-word copies with an exact identical-remap skip.
- No port has needed XMS yet; check for INT 2Fh AX=4300h/4310h before assuming the same.

## Overlays and loaded modules

- **Model the overlay manager from its code**, then replay the model over every trace (call
  order, residency, exactly predicted reads, caller resident on return) with sabotage rules
  that must fail it. Kinds met so far:
  - a linker's thunk manager: make the overlay resident, then `jmp far`; parents reload with
    their children;
  - Borland VROOMM: INT 3Fh stubs patched to far jumps while resident, returns trapped by
    rewriting saved frames along the BP chain, eviction on probation, buffer compaction by
    `rep movsw`, the run-time segment kept in the stub's own word;
  - a game's own manager.
- **The manager is guest code: translate it**, so it loads the bytes into guest RAM as on the
  PC; the runtime only answers its DOS reads. Translate each overlay once as its own module.
  Take an overlay's run-time segment from the manager's own residency record, key dispatch
  rows by CS:IP and module with a residency bit, and lower stub entries as two-form cells
  (trapping and resident).
- **Runtime-loaded drivers** (sound, graphics) are often called through far pointers the game
  copies into its data from an entry table of near offsets, and receive callbacks the same
  way. Map them by their ports and callers, never by file name or strings: a plan that named
  two drawing drivers sound drivers was wrong. A driver loaded at the same paragraph in every
  trace can be translated at a static segment with a residency check.
- Modules loaded with INT 21h AX=4B03 are read by the emulator, not through a guest DOS read:
  the reference maps them at the call ([module mapping](dos-reference.md#the-patch-set)).

## Interrupt delivery

The guest's timer handler runs asynchronously from the Amiga timer interrupt, justified by a
footprint proof (the playbook's
[rule for translators](../playbooks/new-port-playbook.md#rules-for-any-generator-or-translator-transpiled-6502-translated-x86)).
For DOS:

- Drive the Amiga timer from the PIT divisor the guest programs (a CIA-B timer latch scaled
  to the E-clock), not from the beam.
- A handler that reaches STI before its EOI needs an "in service" guard: a tick posted
  meanwhile re-enters it.
- Every handler needs the footprint proof: two INT 08h chains, an INT 15h AH=4Fh keyboard
  intercept called from the BIOS INT 09h model, a Sound Blaster IRQ timed by block length
  over rate.
- The test harness's sync set keeps loop heads; fix it before recording long references
  ([determinism](dos-reference.md#determinism)).

## Guest state that legitimately differs

Uninitialised stack reaches guest state (an `intdos` register block, a local stored on one
branch only), and the port's dead stack holds other bytes than the reference's when its
interrupt handler runs on a private stack. Compare such bytes only under an owner-approved
mask with its own controls, never by loosening the comparison.
