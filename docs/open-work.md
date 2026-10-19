# Open work

## Shared debugger input: remaining work

The native builds have `monitor key`, `fields`, `mouse`, `input` and `harness`, checked by
`scripts/test_fsuae_input.py`; see
[harness commands](reference/headless-fsuae.md#harness-commands-native-builds). The x86_64
build has none of them. Remaining:

- **Mouse buttons and keys are only checked for acceptance** by the smoke test: the stub
  cannot read the CIAs and keeps POTGOR as 0. A side-effect-free read of CIA-A PRA and SDR
  (not ICR, whose read clears it) would let the test read them back.
- **Reusable Python input helpers**: hold and release with an action log, release of
  everything held on cleanup, and a closed-loop pointer move. Gunship and Ferrari Formula
  One each have their own.
- **Ferrari Formula One's private build** (`warp`, survey profiling) should move to the
  shared `mouse` and `input`, which keep its syntax. Carry over its throttle-from-rest
  regression as a documented example: hold the accelerator, verify player movement, release;
  cover simultaneous buttons and their release order.

## FS-UAE overrides and effective configuration

Fix the shared launcher's handling of explicit machine overrides. Prince of
Persia 2 exposed conflicting preset and caller options: raw `uae_*` options
were applied again even when a duplicate was logged as ignored. Requested
NOMMU/JIT settings therefore did not describe the machine that actually ran.
The fake-emulator parser in `scripts/test_fsuae_setup.py` assumes first-value-wins
for every option and cannot detect this failure.

- Define override precedence and emit one effective value for each machine
  setting, including aliases between high-level FS-UAE and raw UAE options.
- Preserve unrelated preset settings, especially CPU frequency and cache policy,
  when changing MMU, JIT or RAM; do not replace the entire preset as a workaround.
- Verify actual CPU/MMU/JIT/RAM configuration from the pinned emulator's effective
  configuration and runtime report, not just arguments or option acknowledgements.
- Cover both launch paths, default presets and explicit overrides. Distinguish
  unsupported JIT builds from a successfully enabled JIT translation cache.
- Correct the override examples in `docs/reference/headless-fsuae.md` alongside
  the implementation.

Acceptance: the duplicate-option failure is reproduced by a regression; defaults
remain intact; explicit NOMMU, cache, JIT and Zorro III selections take effect or
fail clearly when unsupported. A 32 MB Z3 override preserves the selected CPU's
other timing settings. Keep JIT functional checks separate from timing claims.
Prioritize this item among the additions from Prince of Persia 2 because it can
invalidate other projects' measurements without an obvious launch failure.

## Macintosh native pointers above 16 MB

Extend the high-address guidance in `docs/native-port-validation.md` and the
Macintosh runtime reference with Prince of Persia 2's `StripAddress` regression.
Clearing the top byte is valid for tagged Macintosh 24-bit logical addresses,
but truncates native Amiga pointers in high Fast RAM. Alone in the Dark already
preserves native 32-bit pointers; the heap stores handle flags separately.

Reuse the original-paired contract and native fixtures from Prince of Persia 2
commit `b474556` as the reference, retaining only authored fixtures, names and
hashes in shared source. Document the distinction between the original's
logical address mode and the relocated physical address. Share a regression
fixture rather than inventing a helper solely to return an unchanged pointer.

Acceptance: original tagging/CCR behavior is checked separately from native
pointer relocation; native low and high pointers survive all supported dispatch
paths, with registers, condition codes and emulated mode checked. Include both
low-memory and high-memory launches with positive gameplay/quit completion.
The old truncation must be rejected. Keep game-specific checkpoints in the port.

## Installer and icon filename limits

Add a shared release check for the target filesystem's filename limit, including
the `.info` suffix and every archive path component. Prince of Persia 2's
`Prince of Persia 2 Install.info` exceeded a 30-character limit and was truncated
to `.inf` on the reported RAM: installation, hiding the icon. `PoP2 Install.info`
fits. This is a naming problem, not a reason to prohibit installation to RAM:.

Acceptance: authored boundary cases cover names below, at and above the limit,
including drawer icons; the long reported name is rejected and the shortened
name passes. Check the final independently extracted archive member names and
preserve the drawer/icon pairing. Document the supported filename encoding and
filesystem limit rather than assuming every filesystem has identical limits.

## Release startup verification policy

Document and audit the separation between installation verification and normal
game startup. Prince of Persia 2 removed unnecessary whole-file hashing from
ordinary play; release users should not pay for development verification on
every launch. Use its release-build audit as a reference for a reusable check.

- Verify pinned input identities in host or installation tooling before use.
- Put repeated whole-file hashing, tracing and expensive diagnostic audits behind
  an explicit verification/debug build option; ordinary play selects release.
- Retain runtime format, extent, ownership and correctness guards, and named loud
  stops. Disabling expensive verification must not turn malformed inputs or
  unknown operations into successes.
- Check the executable actually packaged, not just the intended build flags.

Acceptance: release/verification build controls prove that expensive diagnostic
paths are absent from the ordinary executable and present when requested;
installation identity checks and runtime rejection guards still pass. Require
matched-workload measurements for any startup-speed claim.
