# WHDLoad hardware debugging: black screens, dumps and CPU caches

Use this supplement when a slave works in an emulator but fails on a real Amiga. Keep all
supplied archives, extracted dumps and diagnostic builds in the project's ignored `tmp/`.
A working quit key establishes that the quit mechanism remains responsive; it does not
establish that the game reached its main loop or that its display code is at fault.

## Read the matching dump first

Record the accelerator/CPU and frequency, RAM, host Kickstart, WHDLoad version, slave build,
options and time spent waiting before quitting. Distinguish the host ROM from the KickEmu
ROM. Read the options and CPU/cache/MMU state from the dump as well as the user's report.

- `.whdl_register` is appended to across runs. It can contain older failures from unrelated
  games. Select the entry matching the slave and capture time before interpreting an error.
- `.whdl_memory`, `.whdl_expmem` and `.whdl_dump` are overwritten. Use the BaseMem/ExpMem
  mappings reported for that capture; do not assume the emulator's usual addresses.
- `.whdl_dump` is an IFF `FORM WHDD` file. Its layout is specified by WHDLoad's
  `Include/whddump.i`; chunk sizes are big-endian and odd-sized chunks have a padding byte.
  Useful chunks include `OPT `, `CPU `, `SLAV`, `MEM ` and `EMEM`. Check the captured slave
  and options rather than assuming which build or icon the user launched.
- An ordinary quit with `CoreDump` can report `Return OK.` and PC `$FFFFFFFF`. That is not
  evidence that the game jumped to an invalid address. Recover context from the interrupt
  frame, saved task registers and stacks, and loaded instructions.

Locate the executable and its live data hunks, following the LoadSeg BPTR chain where
applicable. Read Exec's current, ready and waiting tasks, their signals and saved stacks.
Decode a saved context using the actual Exec/KickEmu save/restore code; do not apply one
stack layout to every CPU or task. Reconcile return addresses, rewritten code and runtime
state to determine whether startup is in DOS, an overlay loader, the intro or gameplay.
Normalize findings to game-hunk offsets before putting them in project documentation.

If an ordinary quit loses essential context, WHDLoad's `DebugKey` is intended to produce a
diagnostic exit. It requires `Expert` and WHDLoad's relocated VBR (unless supported by the
slave); consult the installed `Docs/en/opt.html` before selecting the key. `FileLog` can help
resolve file-access retries. Preserve each run's dump separately.

## Flush after the final executable write

Audit code that modifies instructions, including call stubs located in a **data hunk**.
A flush performed by DOS LoadSeg or `resload_PatchSeg` does not cover writes made afterward.
For an overlay manager, inspect both loading and unloading: one may replace BSRs with JMPs,
while the other restores BSRs. Flush after each completed rewrite and before executing the
modified stub. Verify the hook boundaries and incoming branches, and preserve the original
register restore and return sequence.

Use `resload_FlushCache` (or the existing official KickEmu `_flushcache` wrapper). Its
contract preserves all registers, supports user and supervisor mode on every supported CPU,
and flushes both data and instruction caches on 68040/68060. This matters when modified
instructions are still in the data cache. The reference is the installed WHDLoad
`Docs/autodoc.html#resload_FlushCache`; prefer that API to processor-specific cache opcodes.

A hardware-confirmed example: an Aztec C overlay loader writes JMP stubs and later restores
BSR stubs in place. A real A1200/68040 at 40 MHz, with MMU, 32 MB RAM and WHDLoad 19.2,
black-screened while the quit key worked. RAM already held the JMP, but the CPU had executed
the stale stub and consumed a byte of its target as an overlay index. That selected an
invalid file offset and entered the loader's Seek retry loop. Flushing at the exits of the
completed rewrite fixed startup on that machine. A confirmation on one CPU does not establish
a fix for a separate, untested 68060 report.

## Validate the fix at the right level

An emulator startup pass is a smoke test, not proof of real instruction-cache behaviour.
Use an MMU-enabled emulated CPU to exercise the relevant WHDLoad path and verify from its
log that the MMU is enabled. Keep that correctness test separate from performance work:
the 68040/68060 MMU-loop timing limitations described in the main playbook still apply.

A `NoCache` run can help isolate a cache-dependent failure; WHDLoad documents that it disables
all CPU caches. Treat that as a diagnostic comparison. Confirm the candidate fix on the
failing hardware with caches and MMU enabled as in the original report. Then test the final
production build, including feature-on and feature-off paths, and state precisely which
variant was hardware-tested and which checks were emulated. Never infer hardware FPS from
these startup tests, or claim a second CPU was fixed without testing it.
