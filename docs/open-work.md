# Open work

The following tooling items were reported by F1GP. Both are diagnostic hardening.
Project-specific gameplay and release qualification remain in each project's backlog.

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
