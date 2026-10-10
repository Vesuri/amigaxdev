# Native port crash, installer and release checks

These checks apply to ports that run original 68k instructions with relocated
memory and native service hooks. They complement the [WHDLoad playbook](playbooks/new-game-playbook.md).
The reference implementation is Pokeri: `docs/rom-set.md`, `docs/testing.md`,
`host/native_start_address_test.cpp`, `tools/test_release_installer.py` and
`tools/check_release.py`. No game or dump bytes belong in this repository.

## Diagnose the access before blaming the CPU

Keep the supplied crash archive unchanged under ignored `tmp/`, and extract it
into a separate directory. Record the executable/slave version, CPU, MMU, RAM
configuration and triggering action. Establish the live code and data bases
from the dump before translating addresses to original-program offsets.

Use the recorded access address, direction and data together with the saved PC.
Do not assume the instruction displayed at that PC performed the failed access:
inspect the preceding instructions and exception context. In Pokeri's coin-in
failure, the reported PC mapped to original `$29E0`, a read, but the recorded
access identified the preceding byte write at `$29DC`.

Check the routine's live bytes against the original, its device-address
relocations, every I/O hook descriptor, and the generated patch tables. Recover
the caller from the saved return address and inspect runtime jump stubs as well
as static calls. Add discovered indirect targets to the project's symbol and
entrypoint tables so later disassembly can reach them.

Pokeri's routine at original `$29D2` had one missing device relocation and eight
missing hooks. The coin had already been credited; the crash was a subsequent
video access. That evidence established a hook-coverage defect, not an MMU or
cache defect. Fixing the descriptors retained the original game instructions.

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
scope of each and close the hardware retest only when it has happened. Pokeri
0.91 was confirmed to fix coin-in on the user's A1200 with 68040/40 MHz, MMU and
32 MB RAM; that does not requalify every game path or memory configuration.

## Updating installed ROMs and saves

Before changing an installer because it missed existing files, establish its
actual destination: selected parent, appended game drawer and data subdrawer.
An installation under a different name can bypass an otherwise working reuse
check. Pokeri's installer uses `RAYPokeri/data`; the reported existing install
was named `RayPokeriFI`. Document any required rename and selection of the parent
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
