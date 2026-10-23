# Open work

The following tooling item was reported by F1GP. It is diagnostic hardening.
Project-specific gameplay and release qualification remain in each project's backlog.

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
