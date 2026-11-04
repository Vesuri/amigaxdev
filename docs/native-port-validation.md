# Native port crash, installer and release checks

These checks apply to ports that run original 68k instructions with relocated
memory and native service hooks. They complement the [WHDLoad playbook](playbooks/new-game-playbook.md).
No game or dump bytes belong in this repository.

## Diagnose the access before blaming the CPU

Keep the supplied crash archive unchanged under ignored `tmp/`, and extract it
into a separate directory. Record the executable/slave version, CPU, MMU, RAM
configuration and triggering action. Establish the live code and data bases
from the dump before translating addresses to original-program offsets.

Use the recorded access address, direction and data together with the saved PC.
Do not assume the instruction displayed at that PC performed the failed access:
inspect the preceding instructions and exception context. A reported PC can map to
an original read while the recorded access identifies the preceding byte write.

Check the routine's live bytes against the original, its device-address
relocations, every I/O hook descriptor, and the generated patch tables. Recover
the caller from the saved return address and inspect runtime jump stubs as well
as static calls. Add discovered indirect targets to the project's symbol and
entrypoint tables so later disassembly can reach them.

A missing device relocation or I/O hook shows up as a crash at a later device access,
after the routine's earlier effects have already happened. That evidence establishes a
hook-coverage defect, not an MMU or cache defect; fixing the descriptors keeps the
original game instructions.

## Turn the dump into a regression

Exercise both the original routine and the actual caller through its runtime
stub. Compare the reference instructions with the production prepared hooks,
including every live register, condition codes and ordered device transactions.
Verify original bytes before patching, and keep unknown accesses as loud stops.
A useful regression must reproduce the old fault before passing with the fix.

Include the memory-placement class seen on hardware. A host 68000 model with a
24-bit address bus cannot validate a placement above 16 MiB; use a model with a
full address bus for that case. Cover ordinary placement too. This checks address
handling, not physical cache behaviour. Keep any narrower harness limits explicit.

Separate the evidence: host equivalence, linked Amiga checks, emulated CPU/MMU
runs and a user's physical-machine retest answer different questions. Record the
scope of each and close the hardware retest only when it has happened. A confirmed fix
on one physical configuration does not requalify every game path or memory configuration.

## Macintosh logical addresses and native high pointers

A Macintosh 24-bit logical address can carry tags in its top byte. A relocated
Amiga pointer can use those same bits for real Fast RAM above 16 MB. The emulated
Macintosh address-mode byte does not restrict the native physical address space;
keep handle flags separately rather than embedding them in native pointers.

A `StripAddress` that masks a native pointer with `$00FFFFFF` breaks as soon as data
lands in Fast RAM above 16 MB (for example missing artwork with 32 MB Zorro III RAM).
Preserve the full native pointer, and test it with the shared regression fixture rather
than another identity-function implementation.

`mac-runtime/StripAddressChecks.h` provides 384 native cases: six zero/low/high
pointers, all CCR inputs and both emulated modes. Adapt every real dispatch path
(full, warm and any native entry) to its snapshot callback; check all saved
registers, flags, trap PC advancement and both mode bytes. Its separate 192-case
original contract masks Macintosh tags and checks the System 7.5.5 low-word N/Z
behavior, retained X and cleared V/C. Never require the native physical result to
match the original logical pointer numerically.

Run `scripts/test_strip_address.cpp` for fixture controls: old truncation and
corrupt register/mode/CCR/PC results must fail. That host test validates the checker;
it does not execute a consumer's dispatch. Pin a port's original and native integration
evidence in the port itself, with its addresses and gameplay checkpoints, and require
completed integration and restoration. Qualify both ordinary and high-memory launches
(e.g. 32 MB Z3, NOMMU, JIT off) with actual gameplay progression, clean quit, restored
vectors/patches and WHDLoad return; this is correctness evidence, not a timing claim.

## Cache publication at dynamically installed entries

A registered code pointer need not be ready to execute when it is registered.
An original Macintosh loader can call SetTrapAddress **before** writing its
LoadSeg/UnloadSeg/ExitToShell trampolines. With copyback Fast RAM,
flushing at registration is too early. Publish the newly installed entry at its
first dispatch, after the writes, and avoid flushing on every later invocation.
Keep the original instructions and existing segment-relocation flushes intact.

Heap moves need the same publication. A moved unlocked block can hold code (a
jump-table stub resource), and the original Memory Manager moves blocks with
`BlockMove`, which flushes the caches (inferred). After any service that moved heap
bytes, publish the caches once before original code resumes. MEASURED: without it,
a copyback 68040 ran stale bytes at a relocated stub after `NewPtr` moved it.

Validate with both guest cache bits and the emulator's data-cache model enabled;
CACR alone does not prove the model is active. Use the corrected MMU build from
[headless FS-UAE](reference/headless-fsuae.md#cached-040060-mmu-write-attributes)
and an otherwise identical guest-cache-off control. An uninterrupted cached
startup reproduced the missing-publication crash while that control passed;
debugger stops can flush caches and mask this class of failure. Chip DMA buffer
policy and real-hardware speed/visual checks remain separate obligations.

Under a WHDLoad KickEmu slave, publish code with `CacheControl(0, 0)`, not
`CacheClearU()`. KickEmu routes `exec.CacheControl` to `resload_FlushCache`, and
`CacheControl` clears all caches as a documented side effect without changing a
setting. KickEmu does not patch `CacheClearU`; its own `kick31.s` comment notes
the ROM routine lacks proper setup on CPUs with a copyback cache.

## Self-modifying original code

Original code that writes into its own instructions breaks under a copyback data
cache even when every load and patch is published correctly: the write stays in
the data cache and the instruction fetch reads the old bytes from memory. A typical
case stores a loop limit and a resource ID into the immediates of `CMPI.W #6,D7` and
`MOVE.W #$7E,D0`, then runs them; on a 68040/68060 the stale immediate requests a
resource that does not exist and the game raises its own fatal alert. The symptom
looks like resource or memory exhaustion and moves with code layout.

- Find it with a byte scan of every CODE resource, not only a disassembly's
  defined functions: `LEA d16(PC),An` followed within a few words by a store
  through `An`. No 68k store takes a PC-relative destination, so this pattern
  catches the usual form.
- Prefer removing the self-modification to flushing around it. Keep the values in
  private words below the A5 world: each `LEA`/`ADDQ.L #2`/`MOVE.W
  D0,(A0)` store becomes `MOVE.W D0,d16(A5)` plus `NOP`s, and the consumers
  become same-width `CMP.W d16(A5),D7` and `MOVE.W d16(A5),D0`. Check the original
  bytes, that the address register is dead afterwards, and that the condition codes
  match.

## Updating installed ROMs and saves

Before changing an installer because it missed existing files, establish its
actual destination: selected parent, appended game drawer and data subdrawer.
An installation under a different name can bypass an otherwise working reuse
check, for example an installer that expects `Game/data` facing an existing install
named `GameFI`. Document any required rename and selection of the parent
rather than assuming the installer searches arbitrary drawers.

Offer an explicit **Use existing / Replace** choice when all required files are
present, defaulting to reuse. Reuse skips the source question; replacement asks
for a source and validates the complete set before copying. An incomplete set
asks for a complete source. Keep removal of the entire installation separate
and explain its effect on saves.

With Commodore Installer, `askchoice` returns a zero-based index, whereas
`askbool` returns true for its first choice. Do not change the labels or switch
forms without checking how the result controls copying. The installed Developer
CD reference is under `Reference/DevCon/Orlando_1993/Devcon93.2/Installer/Installer2.16/installer.doc`.

Run the script through the actual supported Installer version. Cover fresh
installation, reuse, replacement, incomplete data, removal and invalid saves.
Use distinct synthetic installed-file bytes and valid source files: identical
fixtures cannot prove whether reuse silently copied or replacement did nothing.
Check which questions were reached, program updates, save preservation and
unrelated files. If the harness substitutes requester answers, describe it as
script-flow coverage; it does not establish interactive requester behaviour.

## Verify the archive users receive

Build with release flags and keep diagnostic executables separate. For a
version-only rebuild, compare binaries after normalizing only the intended
version/date fields to establish that gameplay code is unchanged.

Package only an explicit member list. Exclude original ROMs, Kickstart, WHDLoad,
captured saves and diagnostics; any supplied empty save slots must be authored
independently. Use the shared LHa encoder and independently decompress with
Lhasa. Check member names, CRCs, HUNK/icon headers, slave requirements, version
strings and exact payload identity with build inputs.

Keep the executable, slave, installer, ReadMe, version file and archive date
metadata consistent. Deterministic member order and fixed release-date headers
make repacks comparable. Repackage after ReadMe or installer edits even when the
executable is unchanged, then record the final archive size and SHA-256.

A pushed commit or tag does not upload an ignored local release archive.
Distinguish building and verifying the archive from publishing it as a release
asset, and report which was actually done.

## Filename limits and extracted members

`amigaxdev.release.archive` validates every path component before compression.
The default policy is ASCII names with the classic 30-byte component limit,
including `.info`; a drawer name therefore has at most 25 bytes when it has an icon.
Other target filesystems require an explicit, documented `component_limit`.
The encoder remains ASCII; do not assume a character count equals a byte count for
another encoding. Absolute paths, traversal, control characters and case-insensitive
duplicate file names are rejected.

After independent Lhasa extraction, call
`release.check_extracted_names(directory, expected_members)` with the complete
planned file list, including drawer and installer icons. Exact names detect
truncation and lost drawer/icon pairing: a 31-byte `<long game name> Install.info`
exceeds the default limit where a shortened name fits. RAM: installation is supported within
its filesystem's naming limits; it should not be prohibited as a workaround.

## Installation verification and normal startup

Verify pinned original input identities in host or installation tooling before use.
Ordinary game startup selects a release build; whole-file hashing, traces, exhaustive
fixtures and expensive diagnostic audits require an explicit verification option.
Keep format, extent, ownership and unknown-operation rejection guards active in both
builds, including named failure stops. Do not turn malformed data into success.

Use `release.audit_executable` with explicit diagnostic-symbol patterns and required
runtime-guard symbols. Release must contain none of the diagnostic symbols;
verification must match every requested diagnostic pattern. Supply the project's
pinned deterministic ELF-to-HUNK converter; the audit compares its output byte for
byte with the independently extracted executable. A stale ELF, different converter
or unintended build therefore fails, even if the requested flags look correct.

This audit supplements behavioral tests: prove malformed extents and unknown services
still fail, and installation identity checks still reject changed inputs. Keep the
concrete release policy (symbol patterns, required guards) in the port. Host
fixture tests cover both modes and reject altered executable/guard evidence. Any
startup-speed claim needs matched workloads and measurement; removing diagnostics
alone is not a measured result.
