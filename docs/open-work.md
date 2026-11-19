# Open work

Shared work items. Use the [task index](index.md) for implemented capabilities and their
validation limits. Project-specific gameplay, release and hardware qualification remain in
each project's own backlog.

Add new shared work with a concrete reproduction, the affected component and an
acceptance check. Keep implementation contracts in their canonical reference.

1. **A shared scripted DOSBox-X for DOS references.**
   Reproduction: every DOS port carries its own copy of the same build script, tree check and
   generic patch set ([the DOS reference](reference/dos-reference.md#the-patch-set)), differing
   only in the environment-variable prefix, and each new port copies them again.
   Component: `manifest/` (the DOSBox-X commit and patch hashes), `share/` (the patches with a
   prefix-free variable scheme, the build script, the tree check), the `amigaxdev` package (a
   run driver with pid recording, deadlines and the exit statuses).
   Acceptance: setup builds the patched DOSBox-X under `~/.local/src` from the pinned commit and
   verifies the tree; a port that switches to it reproduces its pinned milestone hashes
   unchanged; a planted edit to a patched file fails the tree check.
2. **A shared OPL2→Paula re-hoster and its host oracle.**
   Reproduction: the re-hoster ([Paula audio](reference/amiga-hardware.md#paula-audio)) is plain
   C with no Amiga headers, and its Nuked OPL checker and renderer are host C++, yet each DOS
   port copies them and applies the others' fixes by hand.
   Component: `share/` (re-hoster, checker, renderer, a vendored Nuked OPL with its licence).
   Acceptance: two ports build the shared copy byte-identically to their own, and the checker's
   level (3 dB) and pitch (10 cent) tolerances fail on planted defects.
3. **RELOC32 block splitting in the shared tools.**
   Reproduction: Kickstart 3.1's LoadSeg refuses a RELOC32 block of 65,536 or more offsets
   ([linking](reference/port-toolchain.md#linking-and-elf2hunk)); only one port has a splitter.
   Component: the `amigaxdev` package (split and check modes), the release checks.
   Acceptance: a synthetic hunk with a 65,839-offset block is split into blocks of at most
   65,535 that relocate identically, the check mode fails on the unsplit file, and a stripped
   release executable compares equal to its full build apart from symbol and debug hunks.
4. **A FAT12 image reader for the install-data helpers.**
   Reproduction: two DOS ports' native installers each add their own FAT12 reader for the
   user's floppy images beside the shared `share/install-data` I/O.
   Component: `share/install-data`.
   Acceptance: host and freestanding 68020 builds list and read every file of a set of 1.44 MB
   images byte-identically to a host FAT reader, and refuse a truncated image and a bad FAT
   chain.
5. **A shared Unicorn x86-16 oracle binding.**
   Reproduction: each DOS port carries its own ctypes binding over `$AMIGA_UNICORN` and its own
   workarounds for the quirks in [x86 real mode](reference/x86-real-mode.md#unicorn-x86-16-as-an-oracle),
   plus a live DOSBox-X single-step tie-breaker.
   Component: the `amigaxdev` package.
   Acceptance: the binding reproduces each listed quirk's workaround in a test (TB flush after
   writes, one REP iteration, engine reopened after an exception), and the tie-breaker agrees
   with the checked real-mode results.
