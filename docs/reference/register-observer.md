# Debugger condition-code observations

The Barto stub must call `MakeSR()` before reading `regs.sr`: the CPU stores
current X/N/Z/V/C flags separately, so the cached SR can describe a previous
instruction. `patches/fsuae-register-observer.patch` materializes SR for both
single-register (`p10`) and all-register (`g`) replies. It changes no CPU flags,
registers other than their derived SR representation, memory or cycle count.
The shared build script applies and fingerprints it on new builds. Existing
emulator installations remain unchanged until explicitly rebuilt.

`scripts/test_register_observer.py` runs the authored `RegisterObserver.s`
fixture twice on each of `a1200-030` and `a1200-040`, with NOMMU/NOCACHE.
It accepts the same input-pin JSON format as `test_cache_observer.py`, an
explicit emulator SHA-256, and a fresh `--work-dir`. Use `--baseline` only for
the unchanged debugger: that arm requires stale readings as its negative
control. The corrected arm compares both packet forms with ten CPU-saved CCR
values and requires the fixture's independent flag assertions, completion word
and normal WHDLoad return. Missing CPU observations, missing completion and a
corrupted completion word must be rejected.

MEASURED: both baseline repeats on both CPUs report
`15,15,15,31,31,31,16,25,10,2`; the corrected debugger and CPU both report
`4,8,0,20,24,16,25,10,2,21`. The sequence exercises X, N, Z, V and C transitions.
The corrected four-run matrix passes twelve evidence-corruption controls.
These are debugger instrument checks, not gameplay or hardware performance measurements.

After a monitor command advances the CPU, GDB still requires
`maintenance flush register-cache`; that separate host-cache issue is unchanged.
