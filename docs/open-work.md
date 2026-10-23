# Open work

The following tooling items were reported by F1GP. They are **backlogged and deferred**;
no shared implementation or installation change is part of the reporting session.
F1GP has deferred 68030 qualification while continuing its other CPU cells.
Project-specific gameplay and release qualification remain in each project's backlog.

## TOOL1 — Investigate indirect directory-drive startup wait

**Component:** native FS-UAE directory-backed drives / indirect hardware traps.

**Reproduction:** use the F1GP deterministic boot route with the pinned native emulator
SHA-256 `ef14ed962d646ca4f85a29c184d86963a9e2a6a2a4de0ed745e8b6e413f6ec3f`,
`a1200-030` (50 MHz), `full+indirect` UAE board, data-cache emulation enabled,
`WARP=1`, `DETERMINISTIC=1`, and both joystick ports disabled. Hold at the reset
breakpoint, take the route's one-field screenshot, press its fire input, and advance
25 fields. The first startup advancement stops making progress before the language
screen. It occurs with the 68030 MMU-capable core and with the verified non-MMU override
`--uae_mmu_model=0 --cpu=68030` (order matters); WHDLoad was requested with `NOMMU`.
Runtime, ROM and game pins and retained captures remain with F1GP.

**Evidence/limits:** host stack samples show the emulation thread in
`filesys_iteration` → `trap_get_bytes` → `call_hardware_trap_back`, waiting on a
semaphore. The valid samples cover `m68k_run_mmu030` and `m68k_run_2ce`.
This locates the wait, not its root cause. Longer deadlines are not proof of progress.
The direct-drive/data-cache-off and normal-speed diagnostic controls used an invalid
CPU spelling (TOOL2) and are rejected as 68030 evidence. No F1GP cache-coherency failure
has been established. The 68020 completes whole races with caches on and off.

**Acceptance:** reproduce under a checked effective CPU/MMU/cache configuration; isolate
why the indirect request fails to complete; add a bounded startup regression covering
both 030 cores with data-cache emulation retained. Validate repeated boot/menu entry and
clean shutdown, plus an F1GP whole-race integration check before lifting its deferral.
Do not substitute disabled data-cache emulation for the required cached validation.
Any runtime change must have reviewed pins and follow the normal shared installation flow.

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
