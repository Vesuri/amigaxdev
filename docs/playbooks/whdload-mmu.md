# WHDLoad MMU compatibility and crash diagnosis

Use this alongside the [profiling playbook](new-game-playbook.md) and the
[hardware crash guide](new-game-playbook-hardware.md). MMU-disabled timing measurements do not
establish compatibility with an MMU-enabled accelerator.

## Keep timing and compatibility checks separate

Retain the fixed-clock setup used for performance comparisons. Add a separate functional
run with a full 68040 or 68060, its MMU enabled, and JIT disabled. For the tested FS-UAE
68040 setup, the relevant options are `--cpu=68040 --uae_cpu_model=68040
--uae_mmu_model=68040 --uae_cpu_24bit_addressing=false --jit_compiler=0`.
Do not use a `-NOMMU` CPU or WHDLoad's `NoMMU` option for this check.

Verify the effective configuration and WHDLoad's saved registers, not just the launch
arguments. In the tested 68040 translation setup, `.whdl_register` must show `TC=8000`;
a run without enabled translation does not test WHDLoad's MMU protection. Do not apply
that exact register value as a 68030 assertion. Require positive scenario completion:
startup, gameplay, file operations and normal quit, including vector restoration.
A timeout or an emulator that merely remains running is not a pass. Treat this as a
functional test, not a fixed-frequency performance measurement; retain real-hardware
confirmation separately and record the CPU, clock, MMU state and memory configuration.

## WHDLoad owns the real vector table

A native executable may use the OS's current VBR to install and restore a handler.
Under WHDLoad, the real VBR belongs to WHDLoad and may point into protected memory.
Do not write into that table or replace VBR to bypass the protection.

For Line-A, set the slave's `WHDLF_EmulLineA` flag and install the handler in the guest
vector at `$28`. WHDLoad forwards the exception there. Save and restore the guest vector
on every ownership transition and normal exit. A dual native/WHDLoad runtime should
select this behavior from its explicit slave/runtime binding, not from CPU type or an
assumption that VBR is zero. Do not generalize the Line-A flag to other exception classes;
check their documented forwarding contracts.

See WHDLoad's [install guidelines](https://www.whdload.de/docs/en/howto.html) and
[EmulLineA contract](https://www.whdload.de/docs/autodoc.html#WHDL_EmulLineA), also available
in the installed developer package's `Docs/` directory.

## Read the complete fault evidence

- Keep the supplied archive unchanged; inspect or extract it under ignored `tmp/`.
  `.whdl_register` can contain appended reports from unrelated games and older runs.
  Select the matching slave and timestamp before interpreting its addresses.
- Use the fault's read/write address and width, exception frame and nearby disassembly
  together. A 68040 write fault can be reported with PC past the offending store; do not
  assume the instruction highlighted at PC performed the reported access.
- Map `.whdl_expmem` with that report's ExpMem base. Match the exact executable and
  resolve each loaded hunk independently: code, data and BSS need not share one relocation
  delta. Publish findings as game code/resource offsets rather than transient addresses.
- Reproduce with the old build, then rerun the same scenario with the correction. If a
  later fault appears, investigate it too. An MMU failure alone does not establish a
  cache bug; `NoCache` is a diagnostic comparison, not a substitute for finding the cause.

## Compatibility structures must have real backing storage

A zero-initialized emulator can hide invalid pointers: an absent compatibility table
may accidentally read harmless zeroes from unrelated memory. Own and initialize the
structures the original code dereferences, even when higher-level service calls already
work. Do not map a foreign platform's low memory over Amiga vectors or Exec state.

Alone in the Dark is a concrete example. Its original stdio close reads a Macintosh
FCB's VCB pointer and volume reference even for read-only files. The port therefore owns
an FCB table and a compatibility VCB; file references are non-overlapping record offsets,
and table updates follow file-model changes. See Alone in the Dark `docs/file-manager.md`
and `tools/test_mac_files.cpp` for the layout contract and lifecycle tests, and
`tools/test_whdload.py --cpu 68040 --mmu` for the functional harness. These are Mac-port
requirements, not structures to add to an ordinary Amiga game.

For scripted input, remember that WHDLoad OS switches can clear a runtime's held-key
state. A controller that intends to keep a key held should reconcile that level after
such a switch, without queuing duplicate key-down events. Distinguish a stalled input
fixture from a game or file-service failure; retain explicit save/load and quit assertions.
