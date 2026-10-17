# Read-only 68040 debugger cache observations

The Barto debugger's ordinary `m` packets read physical memory banks. They do
not consult the CPU data cache or translate a logical address through the MMU.
A copyback line can therefore contain the CPU's current value while a debugger
read reports the old RAM contents. This is a debugger observation limitation,
not evidence that the guest failed to perform its store.

`patches/fsuae-cache-observer.patch` adds an explicit 68040 physical data-cache
overlay. Apply it as the optional patch to the existing build script:

```sh
scripts/build-fsuae.sh fs-uae-cache-observer patches/fsuae-cache-observer.patch
```

The canonical MMU write-attribute, CPU-frequency and harness patches still
apply. The optional observer patch does not change the CPU execution path.
Other emulator installations remain unchanged.

- `monitor memory cache` selects cache-aware physical RAM reads on a 68040.
  Valid data-cache bytes take precedence; misses read the requested RAM byte.
- `monitor memory physical` restores the default raw-bank view.
- ROM and custom-register snapshot handling retain their existing behavior.
- The observer never allocates, flushes, invalidates or writes a cache line.
  It does not change guest registers, cycle counts, page descriptors or ATC state.
- This is **not logical-address translation**. Use it only where the address is
  established as physical/identity mapped. Instruction-cache contents, nonidentity
  MMU mappings and other CPU models are outside this mode's validated scope.
- Debugger writes remain unsupported. Put stimuli in the authored fixture or
  use guest input; debugger readback is not proof that a write reached the CPU.

The existing 040 debug-cache helper also needed to retain the original byte
address on a miss instead of reading the aligned cache-line base, and to report
cache hits through its `cached` output parameter. The observer uses byte reads,
including ranges crossing cache lines; it does not claim validation of arbitrary
unaligned word/long helper calls.

After `monitor fields`, run `maintenance flush register-cache` before using
registers: the monitor command advances the CPU without invalidating GDB's host
register cache. This command affects GDB only. Disable GDB's `stack-cache` and
`code-cache` when comparing the two memory views.

## Controlled fixture

`scripts/test_cache_observer.py` assembles `share/fixtures/CacheObserver.s` and
runs two repeats of MMU on/off × data cache on/off on `a1200-040`. It requires an
explicit emulator hash and a JSON input manifest. Manifest keys are environment
variable names, optionally followed by a relative path; `GDB` means the resolved
`m68k-amiga-elf-gdb`. Required pins include the compiler, debugger, WHDLoad,
Kickstart, Workbench, launcher and slave header; also pin the included NDK files.

```sh
. "$AMIGA_SHARE/env.sh"
python3 scripts/test_cache_observer.py \
  --emulator "$AMIGA_SHARE/fs-uae-cache-observer/fs-uae" \
  --sha256 EXPECTED_SHA256 --input-pins INPUT_MANIFEST \
  --work-dir tmp/cache-observer
```

Use `--baseline` with the pinned unpatched emulator to reproduce stale raw
reads. All stimuli are compiled; no debugger memory/register writes are used.
The fixture initializes a varying byte pattern while uncached, establishes its
cache policy, writes two values and a longword spanning a line boundary, and
loads values into CPU registers. It pauses at two bounded native observation
windows, changes one value between them, then checks its own values and an
untouched guard before a positive completion marker and normal WHDLoad return.

WHDLoad NOMMU leaves CACR disabled, so this authored experiment explicitly sets
CACR during setup for each matrix arm. The fixture checks actual TC/CACR and the
emulator configuration. After the native completion breakpoint, teardown restores WHDLoad’s prior CACR
before returning through its API. No policy change or flush occurs between the first
observed stores and native completion. The cache-on MMU case must retain stale
raw RAM both before and after the cache-aware read. Cache-off arms must match
raw RAM. Uncached Chip RAM, untouched bytes, cache misses, partial/cross-line
ranges and a second native store serve as controls. Eight evidence mutations
per corrected run must be rejected, including wrong/missing CPU observations,
wrong data/address, writeback, Chip data, completion and disabled cache emulation.

The fixture is an instrument check, not a game-performance or hardware claim.
Port-specific original-paired save/audio/exit checks remain with each port.

MEASURED: two corrected repetitions of all four combinations pass (eight runs,
64 rejected evidence mutations). A matching four-run baseline reproduces stale
raw reads only with both MMU and copyback data caching enabled. The cache-aware
view matches all 96 authored bytes in both phases of every corrected run, while
the raw view is unchanged by observation. NOMMU/cache-on has no raw/cache divergence
in these observations. Prince of Persia 2 retains the evidence hashes and separate
original-paired release observations.
