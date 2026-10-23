# Open work

The following tooling items were reported by F1GP. TOOL1 blocks deterministic captures
on every data-cache preset. TOOL2 and TOOL3 are diagnostic hardening. Project-specific
gameplay and release qualification remain in each project's backlog.

## TOOL1 — Deterministic mode deadlocks with the indirect UAE board

**Component:** native FS-UAE directory drives in deterministic mode
(`filesys_hsync`, `src/filesys.cpp`) and indirect hardware traps (`src/traps.cpp`).

**Cause (from the source; matches every host sample):** `--deterministic=1` makes
`filesys_hsync` process directory-drive packets on the emulation thread during
horizontal sync (`run_filesys_iterations` → `filesys_iteration`). With
`uaeboard=full+indirect`, the packet handler's memory access (`trap_get_bytes`) goes
through `call_hardware_trap_back`. That function asks the emulated 68k to run the trap and
polls, with 100-ms semaphore timeouts, until the trap completes. The emulated 68k runs on
that same thread, so the trap never completes. The hang happens when the first drive
starts (`FS: dh0 ... starting..`), before any guest program runs. The code path is
upstream FS-UAE's deterministic filesystem handling; none of our patches touch
`filesys.cpp`.

**Why every data-cache preset hits it:** `fsuae_common.sh` adds `full+indirect` whenever
it emulates a data cache (030/040/060). The board is genuinely required there. Without it,
`main.cpp` turns data-cache emulation off ("Data cache emulation requires Indirect UAE Boot
ROM") while `debug.uae` still records `cpu_data_cache=true`. Switching to the direct
board is therefore not a workaround.

**Minimal reproduction:** pinned emulator
SHA-256 `ef14ed962d646ca4f85a29c184d86963a9e2a6a2a4de0ed745e8b6e413f6ec3f`. Boot a
directory `DH0` whose `S/Startup-Sequence` is `Echo >DH0:ok "booted"`, with `WARP=1`,
no window and no Workbench floppy, then wait up to 45 s for the file. No game is needed.

| Preset / override | Deterministic | Result |
| --- | --- | --- |
| `a1200-fast` (direct board) | on | boots in 2 s |
| `a1200-030`, `a1200-040`, `a1200-060` | off | boots in 2–3 s |
| `a1200-030`, `a1200-040`, `a1200-060` | on | no file after 45 s; emulation thread in `filesys_hsync` → `filesys_iteration` → `trap_get_bytes` → `call_hardware_trap_back` |
| `a1200-fast` + `--uae_uaeboard=full+indirect` | on | hangs the same way |
| `a1200-030` + `--uae_cpu_data_cache=false` (board stays indirect) | on | hangs the same way |
| `a1200-030` + `--uae_uaeboard=min` | on | boots, but data-cache emulation was turned off |

So the trigger is deterministic mode together with the indirect board. The CPU, MMU and
data cache don't matter. F1GP's game, slave and cache option are not involved. With
deterministic mode off, F1GP starts on all six 030/040/060 setups (MMU and non-MMU)
with caches on, but those runs don't repeat exactly. `scripts/test_fsuae_repeat.py` boots
ROMs only, with no directory drive or data-cache preset, so it doesn't cover this case.

**To do:**

1. Fix the deterministic path for indirect traps. Candidates, none tried yet:
   - In deterministic mode, process the packet with direct host memory access, then
     invalidate the emulated data cache for the memory it wrote, or all of it. This is the
     coherency the indirect board exists to provide.
   - Hand the packet to the existing trap thread and accept its completion only at a
     later, emulated-time point.

   Check that completion timing depends only on emulated state, never on host thread
   scheduling.
2. Carry the change as a reviewed patch, with new pins and the normal installation flow.
3. Add a bounded regression for the reproduction above, covering each data-cache preset
   with deterministic mode on. Check data-cache emulation in the emulator log, not in
   `debug.uae`. Extend `test_fsuae_repeat.py` with a directory-drive boot on a data-cache
   preset, so two runs must still agree exactly.

**Acceptance:** every data-cache preset boots a directory drive under `DETERMINISTIC=1`
with data-cache emulation in effect. Two runs repeat exactly. Behaviour without
deterministic mode is unchanged. Finally, the F1GP integration check: a deterministic
030/040/060 Quick Race with caches on, repeated exactly, followed by a clean F10 quit.

## TOOL2 — Reject unsupported CPU spellings and verify effective settings

**Component:** shared launcher CPU option validation and emulator configuration checks.

**Reproduction:** request `--cpu=68030-NOMMU --uae_mmu_model=0` on `a1200-030`.
The pinned emulator accepts the option text but reports effective `CPU=68020`, not 68030.
The `-NOMMU` spelling supported on 040/060 must not be assumed valid on 030.
The supported 030 override is `--uae_mmu_model=0 --cpu=68030`, in that order.

**Current mitigation:** F1GP rejects mismatched effective CPU/MMU reports before its
matrix route and retains the effective configuration. This is a local mitigation,
not a shared fix.

**Acceptance:** unknown CPU spellings fail clearly before measurement; supported presets
and MMU overrides retain their intended effective CPU/FPU/MMU/JIT/cache settings. Extend
the shared configuration tests with the rejected spelling and the valid 030 override.
Verify effective settings rather than treating command-line acknowledgements as evidence.
`debug.uae` records requested values: when `main.cpp` turns data-cache emulation off
(for example without the indirect board), `debug.uae` still says
`cpu_data_cache=true`. Check the emulator log for that message too.

## TOOL3 — Reject stale screenshots/traces after debugger failure

**Component:** shared `amigaxdev.gdbserve` screenshot/profile collection and consumers.

**Reproduction:** leave a previous successful trace at the output filename, disconnect
or terminate only the verified owned emulator, then request a screenshot/profile.
A debugger error that produces no new trace can leave the old file available for parsing,
misrepresenting the old image as a fresh field. F1GP's failed-startup diagnostics exposed
misleading screen timeouts and stale failure screenshots through this path.

**Current mitigation:** F1GP's route screenshot helper removes the previous trace and
requires a newly produced one-field capture. Its matrix runner no longer requests failure
screenshots from a disconnected target. Shared `shot`/profile behavior remains to audit.

**Acceptance:** pre-existing output cannot satisfy a failed capture. Missing, partial or
wrong-field-count output and debugger disconnects must fail explicitly without a success
image. Add adversarial stale-file/disconnection tests and successful capture controls;
ensure failures do not silently advance routes or reuse evidence from another run.
