# Building a port with the shared toolchain

How the source ports build C, C++ and assembly into an Amiga executable, a WHDLoad slave and a
release archive, and how they keep a host (SDL) build beside it. Paths and variables are in
[the shared environment](../environment.md); running the result is in
[headless FS-UAE](headless-fsuae.md); code generation for speed is in
[m68k optimisation](m68k-optimisation.md).

- [The toolchain](#the-toolchain)
- [Compiler flags](#compiler-flags)
- [Optimisation levels](#optimisation-levels)
- [Assembler](#assembler)
- [Linking and elf2hunk](#linking-and-elf2hunk)
- [Startup, runtime and the framework](#startup-runtime-and-the-framework)
- [Memory helpers](#memory-helpers)
- [Chip data and retained sections](#chip-data-and-retained-sections)
- [Link audits](#link-audits)
- [Rebuilds and flags](#rebuilds-and-flags)
- [Development and release builds](#development-and-release-builds)
- [WHDLoad slaves for ports](#whdload-slaves-for-ports)
- [Release archives and disk images](#release-archives-and-disk-images)
- [The host build](#the-host-build)
- [Analysis tools](#analysis-tools)

## The toolchain

`make setup` installs BartmanAbyss amiga-debug 1.8.2: `m68k-amiga-elf-gcc` 15.1 with binutils
and gdb, `elf2hunk`, `vasmm68k_mot` and the gdb-stub FS-UAE. They are matched builds (DWARF,
gdb and stub agree), which is what makes source-level debugging work. Don't install per-repo
copies.

- Every build sources `amiga/env.sh` **in the same shell command**; it puts the toolchain on
  `PATH`. Makefiles default each tool with `?=` so they also work without it.
- **No spaces on the toolchain path.** GCC's LTO link bakes the install path into
  `COLLECT_LTO_WRAPPER` and `posix_spawnp`s it; a space breaks the spawn. Hence `~/.local`.
  Project paths often contain spaces (`Rescue on Fractalus`): quote every path in recipes, and
  resolve symlinks with `pwd -P` where gcc sees them.
- The freestanding CRT is `$AMIGA_PREFIX/support/gcc8_{a_support.s,c_support.c,c_support.h}`.
  Makefiles find it next to gcc: `SUPPORT = $(dir $(shell which $(CC)))../../support`.
  NDK headers for C are `$AMIGA_TOOLCHAIN/m68k-amiga-elf/sys-include` (`SDKDIR`); vasm uses `$NDK`.
- macOS ships GNU Make 3.81: no same-second timestamp tricks, no newer functions (Slicks keeps
  its Makefile 3.81-safe with stamp files).

## Compiler flags

The common set, from Revs, Rescue on Fractalus, Vette, Pokeri and Slicks:

```make
CCFLAGS  = -g -MP -MMD -m68000 -msoft-float $(OPT) -nostdlib \
           -fno-tree-loop-distribution -ffunction-sections -fdata-sections $(WARN)
CPPFLAGS = $(CCFLAGS) -fno-rtti -fno-exceptions -fno-use-cxa-atexit -std=gnu++17 \
           -fpermissive -Wno-write-strings -Wno-pointer-arith \
           -include "$(FRAMEWORK)/SASCCompat.h" -I"$(FRAMEWORK)" -I"$(FRAMEWORK)/compat-include"
ASFLAGS  = -mcpu=68000 -g --register-prefix-optional -I"$(SDKDIR)"
```

- **CPU.** `-m68000` for an A500 target: `-m68020` emits scaled indexing, 32-bit
  `mulu.l`/`divu.l` and bit-field instructions, which trap on a 68000. 68000 code runs on every
  later CPU. A 68020 target says so (`-m68020`, Slicks and Secret Weapons of Luftwaffe;
  `-m68020 -mtune=68020`, Alone in the Dark). Downwell keeps 68000 as the baseline and allows
  newer-CPU code only as a runtime-selected option.
- **`-msoft-float` always.** The toolchain defaults to hard float for `-m68020`, which emits
  line-F FPU instructions. Then audit that no soft-float helper is linked
  ([link audits](#link-audits)).
- **`-g` always**, in every build: debugging and every `.gdb` probe read the ELF, and the
  executable can drop its symbols at conversion.
- `-ffunction-sections -fdata-sections` with `--gc-sections` drops framework routines a game
  doesn't call.
- `-fno-tree-loop-distribution` is in every port's flags.
- Slicks adds `-Wall -Wextra -Werror` to its own code. Transpiled cores (Revs, Rescue on
  Fractalus) silence the warnings the generator produces in `CORE_CFLAGS` instead.

## Optimisation levels

Ports default to `OPT ?= -O2 -fomit-frame-pointer` and give the hot units a separate,
higher level (`NATIVE_OPT`, `GAMEPLAY_CFLAGS`). `make OPT=-O0 NATIVE_OPT=-O0` gives clean
backtraces.

| Choice | Measured | Project |
|---|---|---|
| `-O3` vs `-O2` on the native surface | `-O3` 4.5 ms (6%) faster a frame | Revs |
| `-funroll-loops` on top of `-O3` | nothing measurable for +43 KB; dropped. Loops that need unrolling are hand-unrolled or asm (`#pragma GCC unroll` is not reliable: [m68k optimisation §4](m68k-optimisation.md#4-loops-and-memory-access-in-c)) | Revs |
| `-fno-tree-loop-distribute-patterns` on hot code | without it a short constant fill became two `memset` calls per segment, ~368 cycles each: 24.63 → 35.38 ms | Revs |
| `-fno-tree-loop-vectorize` on hot code | without it GCC widened a byte fill and spilled table addresses: it cost 7.55 ms | Revs |
| `-fno-unroll-loops -fno-unroll-all-loops` everywhere | code-size control on a 68000 | Pokeri |
| `-flto` | used for the whole program; needs the space-free toolchain path | Downwell |

Rescue on Fractalus, Vette and Alone in the Dark still use `NATIVE_OPT = -O3 -funroll-loops`
without a measurement against plain `-O3`. Price an option the way Revs did, on the hot unit,
before adopting it ([measurement method](measurement-method.md)). `#pragma GCC unroll 1` does
not stop the pattern recogniser: it runs before unrolling. Validate a narrowed level range in
the Makefile (Downwell rejects anything but `-O2`, `-O3`, `-Os`).

## Assembler

Hand-written code goes through vasm; gcc's `as` handles the CRT and small `.s` with GNU syntax.

```make
VASMFLAGS = -m68010 -Felf -quiet -x -no-opt -nowarn=62     # 68000 targets
VASMFLAGS = -m68020 -Felf -quiet -x -no-opt -nowarn=62     # 68020 targets
```

- **`-no-opt` is load-bearing** for hand-written code: it keeps encodings and branch sizes
  exactly as written, so PC-relative jump tables don't move. Mark in-range hot branches `.s`
  yourself, or they assemble long.
- `-m68010` on 68000 targets (Revs, Rescue on Fractalus, Vette) only because the framework's
  `getVBR` uses `movec vbr,d0`; it is behaviour-neutral on a 68000, and the post-68000
  instruction audit below still applies. Pokeri assembles with `-m68000` (the framework can emit
  the `movec` as `dc.w $4e7a,$0801`). 68020 targets (Slicks, Alone in the Dark, Secret Weapons of
  Luftwaffe) use `-m68020`.
- Generated assembly is different: Secret Weapons of Luftwaffe assembles its translator output
  with vasm's default optimisations (branch sizing) and `-m68020`. vasm then drops a `bra` to
  the next instruction, so labels can share an address. Limits of vasm 1.9 on a large
  generated program:
  - Branch sizing may never converge ("maximum number of passes reached"). Triggers seen:
    a `bra` to the next line; any `cnop` after the start of the program; thousands of
    unsized branches into code-sized stubs. The generator emits no branch to the next line,
    sizes hot branches itself (`.s` within a safe estimate, else `.w`) and sizes alignment
    pads by assembling and reading back label addresses (fixed `ds.b`).
  - An out-of-range `(d16,An)` becomes `(bd.l,An)` for `move`, `add`, `cmp`, `and`, `tst`
    and `chk`, but `mulu`/`muls`/`divu` fail with error 2030 ("displacement out of range").
    Keep their displacements within 16 bits, including under test plants that shift them.
- `-x` makes undefined symbols errors rather than externals.

## Linking and elf2hunk

```make
LDFLAGS = -Wl,--emit-relocs,--gc-sections,-Ttext=0,-Map=$(OUT).map
.DELETE_ON_ERROR:
$(OUT).exe: $(OUT).elf ; elf2hunk $< $@ -s
```

- `-Ttext=0 --emit-relocs` gives `elf2hunk` what it needs to write relocatable HUNKs; gdb loads
  the ELF and the stub supplies the load base.
- `elf2hunk -s` drops the HUNK_SYMBOL table (11% of a Rescue on Fractalus probe build). Nothing
  reads it: every debugger reads the ELF. Keep `SYMS=1` to retain it if a tool ever needs it.
- `.DELETE_ON_ERROR` (Slicks, Secret Weapons of Luftwaffe): a failed `elf2hunk` must not leave a
  truncated executable that looks up to date.
- Write `objdump --disassemble --no-show-raw-ins -S` of the ELF to `$(OUT).s` after every link;
  audits and reviews read it.
- **`elf2hunk` can't represent `R_68K_PC16` across objects.** A `bsr` to another object must be
  a `jsr` (the framework Makefile rewrites cross-object `bsr _blitter*`). Intra-object branches
  stay PC-relative.
- Keep the ELF and map with every executable you measure or release; samples and dumps are only
  readable against the matching ELF.

## Startup, runtime and the framework

- The CRT's `_start` runs the constructors (`init_array`), calls `main`, runs `fini_array` and
  returns. It reads `SysBase` from `$4` and opens no library, so it is Kickstart 1.3-clean
  (checked for Rescue on Fractalus' `kick13` slave). A project with its own entry renames the
  shared one at compile time (Pokeri: `-D_start=pokeriUnusedSharedStart`).
  The replacement must be the first byte of the first code hunk, where DOS enters: link its
  object first and fail the build unless `objdump -t` shows `_start` at 0 in `.text` (SWOTL
  `amiga/Makefile`).
- Most ports build on the **dA JoRMaS C++ framework** (`AmigaHardware`, `Bitmap`, `CopperList`,
  `Sprite`, the module player), vendored per project under `src/platform/amiga/framework/`.
  Its `GCC-PORT.md` is the full guide; the points that matter for a new port:
  - `SASCCompat.h` is force-included on GCC only. It maps `__chip` to a `.MEMF_CHIP` section,
    turns `__far`/`__saveds`/`__regargs`/`register __d0` into nothing, and turns `__inline`
    into nothing (the framework defines those functions out of line). `__asm` stays: the NDK
    library-call macros need it.
  - `GCCRuntime.cpp` supplies `operator new`/`delete` over `AllocMem`/`FreeMem`,
    `__cxa_pure_virtual`, a few libc functions and the level-3 interrupt trampoline;
    `compat-include/` has minimal `stdlib.h`, `limits.h`, `math.h`.
  - The SAS/C `*Assembler.s` are bridged with `sed` at build time (sections, mangled names,
    small-data base, cross-object `bsr`) and reached through register-marshalling wrappers.
    `NO_ASSEMBLER=1` builds the portable C++ bodies instead.
  - Flags written by an interrupt must be `volatile`, or `-O2` can spin forever or duplicate a
    `bltsize` start. An assembly `Scc` result (`$FF`) must enter C++ as an integer byte and be
    normalised with `!= 0`, never bound to `bool`.
- Assets are embedded with `.incbin` in an assembler file, which gives exact symbol names and
  chip/data section control (the GCC equivalent of SAS/C's `Bin2Hunk`).

## Memory helpers

The support library's `memset`/`memcpy`/`memmove` are byte loops (24–40 cycles a byte). Revs'
`fastmem.c` replaces them with longword loops, linked with `-Wl,--wrap=memset` (and the
others; Pokeri wraps `memset` too). Wrapping at the link is what reaches the calls GCC emits by
itself from a constant-store loop.

- **Compile the replacement with `-fno-tree-loop-distribute-patterns`.** Otherwise GCC turns its
  own short byte loops back into a `memset` call, `--wrap` redirects that into
  `__wrap_memset`, and any fill of 1–7 bytes recurses until the stack dies. The sign is
  `jsr <__wrap_memset>` inside `__wrap_memset` in the disassembly.
- Compile it `-O2 -fno-unroll-loops`: its loops are already unrolled by hand, and unrolling
  adds dispatch ahead of the first store on the short fills a port does.

## Chip data and retained sections

- `__chip` puts a variable in a `.MEMF_CHIP` section, which GCC emits as data even without an
  initialiser. Rescue on Fractalus links it `(NOLOAD)` with a supplementary script
  (`INSERT AFTER .data`, so `-Ttext=0` still applies); `elf2hunk` writes a chip BSS hunk,
  saving 14.6 KB of zeros (4.8% of the executable).
- **Then a static initialiser on a `__chip` variable is silently discarded.** Fill chip data at
  run time, and fail the link if any object contributes a nonzero byte to `.MEMF_CHIP`
  (Rescue on Fractalus `tools/check_chip_bss.py`).
- **The `$VER:` string has no references**, so `--gc-sections` drops it unless its section is
  `SHF_GNU_RETAIN`. `__attribute__((retain))` is ignored on this target; set the flag in the
  assembler source. Check for the string in the executable after `elf2hunk` and delete the
  output if it is missing (Rescue on Fractalus, Revs).
- **`.incbin` dependencies are invisible to `-MMD`.** List them in the Makefile: a regenerated
  blob that didn't trigger a rebuild shifted Rescue on Fractalus' music by one byte.

## Link audits

Run them on every link, from the ELF's symbols and disassembly, and fail the build. A
regression is then caught when it is introduced, not found in a profile months later.

| Audit | Fails on | Why | Project |
|---|---|---|---|
| mul/div | `__mulsi3`, `__(u)divsi3`, `__(u)modsi3` | the 68000 has no 32-bit multiply or divide: each call is ~200–600 cycles. Use 16-bit helpers ([m68k optimisation](m68k-optimisation.md)) | Revs, Vette, Pokeri |
| 64-bit helpers | `__(ashl\|ashr\|lshr\|mul\|udiv\|div\|umod\|mod)di3` | unexpected 64-bit arithmetic | Downwell |
| post-68000 instructions | `bf*`, `divsl`/`divul`, `extb`, `cas`, `chk2`, `move16`, `movec`, `rtd`, ... in the disassembly | a 68000 target must not contain them | Downwell |
| soft float | any `__*sf*`/`__*df*` helper symbol | no FPU code and no soft-float library in the runtime | Alone in the Dark |
| alignment | `O .data/.bss` objects of 4+ even bytes at an address not divisible by 4 | GCC aligns 32-bit data to 2; a misaligned longword costs a second 68020 bus cycle, and unrelated edits move neighbours (removing a few globals slowed cold startup 8%). Declare them `alignas(4)` | Pokeri |
| probe symbols | a `PROBE_SYMS` name that is not a data symbol | `--gc-sections` drops unused counters and gdb then prints code bytes. Make each a GC root with `-Wl,--undefined=SYM` | Revs, Vette, Alone in the Dark |
| release contents | diagnostic symbols in a `DIST=1`/`RELEASE=1` link; missing `$VER` | no instrument ships | Revs `dist-audit`, Pokeri `check_release_code.py` |
| chip BSS | nonzero bytes in `.MEMF_CHIP` | see above | Rescue on Fractalus |
| asset ownership | assets linked that should be loaded at run time | memory budget | Downwell |

Grep the symbol table (`objdump -t`), including undefined references, rather than the
disassembly text where you can; the instruction audit is the exception.

## Rebuilds and flags

- **Make does not track `-D` values**, and older port Makefiles (Revs, Rescue on Fractalus)
  track no header dependencies either. A partial rebuild then links stale objects into a
  working-but-wrong binary, often a struct layout mismatch that shows up as unrelated
  corruption. `make clean` after any flag change or edit to a widely included header, and
  treat a regression right after one as a stale build first.
- New Makefiles should use `-MMD -MP` and include the `.d` files, and record build modes in
  stamp files that objects depend on (Slicks `obj/*-$(MODE).stamp`; Downwell's
  `hunk-options` file reconverts the executable when `STRIP` changes without a clean build).
- Reject impossible flag combinations with `$(error)` (Pokeri, Downwell) instead of building
  something that measures the wrong thing.
- Don't rebuild while an emulator run is using `out/` ([headless FS-UAE](headless-fsuae.md#pitfalls)).

## Development and release builds

- Development builds keep probes, replay, self-tests and diagnostic shortcuts behind flags; a
  release flag (`DIST=1` in Revs, `RELEASE=1` in Pokeri) removes them, and the release audit
  proves it. Clean when switching.
- Keep diagnostic executables out of the release staging area; a previous diagnostic build can
  occupy the release file name.
- Build the release twice from clean and require byte-identical executables (Slicks
  `make release-check`).
- Release archive checks (member list, CRCs, independent decompression, version strings,
  publishing) are in [native port validation](../native-port-validation.md#verify-the-archive-users-receive).

## WHDLoad slaves for ports

A port is an AmigaDOS program whose takeover is OS calls (`AllocMem`, `OpenLibrary`,
`LoadView`, interrupt vectors), so its slave is a **KickEmu** slave: WHDLoad boots a real
Kickstart in its own memory and the slave `LoadSeg`s the unchanged executable as a CLI
process. A plain slave has no OS. Rescue on Fractalus `docs/whdload-slave.md` §0 records the
alternatives that were declined (an OS shim in the game, a fake exec in the slave).

- `kick13` when the program is 1.3-clean: its ROM image is 256 KB against 512 KB for
  `kick31` (Rescue on Fractalus, Revs). Vette uses `kick31`; Slicks adapts Vette's slave and
  adds `INITAGA`, which its direct AGA platform needs.
- Assemble the slave with vasm against `$WHDLOAD/Include` and the KickEmu sources in
  `$WHDLOAD/Src/sources/whdload` instead of vendoring copies.
- Ship the same executable as the standalone build; the slave patches only explicit,
  magic-tagged configuration blocks.
- Slicks' slave details for an AGA port: mounts `data/`, sets PROGDIR and a null-terminated
  argument string, supplies a 16 KiB stack with `StackSwap`, restores and unloads on return.
  Don't use the SDK's `kick31.s` `STACKSIZE` option: its A600 ROM patch overwrites the wrong
  opcode (Vette).
- For a program that parses its arguments with `ReadArgs`, start it with `RunCommand` (16 KiB
  stack) instead of `SetArgStr`, `StackSwap` and a call of the entry: DOS allocates and swaps
  the stack and puts the line in `Input()`'s buffer, where `ReadArgs` reads it (SWOTL).
- Each OS switch under WHDLoad is a visible pause and each write adds WHDLoad's write delay:
  write whole files, only when their bytes changed (Slicks).
- Test under WHDLoad in FS-UAE and judge from WHDLoad's core dump, not from the screen
  (Revs, Slicks, Alone in the Dark `tools/test_whdload.py`). WHDLoad sees `TIMEOUT` and the
  QuitKey only through a moved VBR, so such a run needs a 68010 or later; `FILELOG` on a 68000
  can outlast the timeout before the game starts.
- Choose a QuitKey the game doesn't use (Revs: keypad `*`, because F10 is a game key).
- The WHDLoad playbook covers slave building and hardware failures in depth:
  [new-game playbook §10](../playbooks/new-game-playbook.md#10-building-and-gating-patches),
  [hardware debugging](../playbooks/new-game-playbook-hardware.md),
  [MMU compatibility](../playbooks/whdload-mmu.md).

## Release archives and disk images

- Create archives with LHa for UNIX (`$LHA`); Lhasa (`lha` from Homebrew) can only extract,
  which makes it the independent checker. Format rules: playbook
  [§13](../playbooks/new-game-playbook.md#13-release-archives).
- Test the Install script under the real Installer 43.3 (`$INSTALLER43`) in FS-UAE, with the
  Workbench floppy for `C:` and `Libs:` (Revs `test_installer.py`). A boot without `ENV:` hangs
  at the first `getenv`; Installer's `textfile` hangs if its file exists. What the harness
  covers and doesn't: [native port validation](../native-port-validation.md#updating-installed-roms-and-saves).
- Refuse to package any member that carries original bytes (Revs scans every member for the
  original engine's blocks).
- ADFs: `xdftool` (amitools, in the shared Python) reads and writes them; `exe2adf` and
  `Shrinkler` are installed too. No port ships a disk image yet.

## The host build

Each port keeps a host build of the same core sources: Clang, GNU Make, SDL2 from Homebrew
(`pkg-config sdl2`), `src/platform/sdl` beside `src/platform/amiga`.

- It is a development reference, not an authority. Fidelity comes from the original under a
  reference emulator, performance from FS-UAE ([validation harness](validation-harness.md)).
  Revs' host build has no renderer at all: it exists for differentials and proofs.
- Debug and release variants (`make` at `-O0 -g`, `make RELEASE=1` at `-O2 -g`, Rescue on
  Fractalus); `-MMD -MP` with the object tree mirrored under `build/` (Downwell).
- **The host is little-endian, the Amiga big-endian.** Anything that aliases a byte array as
  `uint16_t*`/`uint32_t*` passes on the host and is byte-swapped on the target. Revs
  `make endian-lint` greps for it, with an explicit marker for the legitimate exceptions.
- Code that only the Amiga build compiles has no host oracle; it needs its own proofs (Rescue on
  Fractalus `make hostproof`).

## Analysis tools

- **Ghidra** (`brew-extras`) is linked as `~/.local/share/ghidra/ghidra_<version>_PUBLIC`;
  projects symlink `tools/ghidra` to it and keep their own project database in `tools/ghidra-proj/`
  (ignored, not disposable: it holds the annotations).
  - Set `JAVA_HOME` to Homebrew's `openjdk@21`; `/usr/bin/java` is a stub.
  - Ignore the symlink as `tools/ghidra` with no trailing slash: a trailing slash doesn't match
    a symlink to a directory.
  - Don't open a project in the GUI while headless uses it; Ghidra locks it.
  - Start it from the project root with `-scriptPath "ghidra_scripts;$AMIGA_GHIDRA_SCRIPTS"`:
    the shared scripts (`ExportListing`, `DumpCallGraph`, `Mac*`) are in AmigaXDev.
  - Run `MarkEntries` as a `-preScript` so analysis disassembles the new entries;
    `-noanalysis` only for export-only runs; `-process NAME` instead of `-import` for an
    existing program.
  - Track only the curated `disasm/symbols.csv`; listings and images are regenerable.
- **Unicorn** for differential oracles: use the shared `$AMIGA_UNICORN` build, not Homebrew's,
  which dies with SIGILL on arm64 where an add/subtract-with-borrow folds to a constant.
  Unicorn's 68020: write SR before A7 (A7 is the active stack pointer).
- `brew install` on a managed Mac may raise a privilege prompt: let the user start installs.

### Deterministic stripped HUNK padding

MEASURED in Prince of Persia 2 release qualification: the bundled converter can
write an uninitialized extra word after a section whose size is divisible by
four. Two otherwise identical stripped executables differed only in the word
after `.init_array`. The upstream converter writes `(size + 4) / 4` words but
allocates only the rounded section length. This can read beyond its allocation.

`patches/elf2hunk-zero-padding.patch` makes that allocation match the existing
output size and zeroes it. Hunk sizes, section data and relocation records stay
unchanged. Upstream source is pinned as `elf2hunk-86fdfadb.tar.gz` in
`manifest/downloads.tsv` (revision
`86fdfadb3ddab50b9457f5018c36c796c716cc13` of
[BartmanAbyss/elf2hunk](https://github.com/BartmanAbyss/elf2hunk)).
`make elf2hunk-fixed` (also part of `make setup`) verifies the archive, applies
the pinned patch in a fresh build directory and installs
`$AMIGA_SHARE/elf2hunk-fixed`, preserving any differing existing file in
`.replaced/`. The bundled tool stays unchanged. Ports select the fixed tool through
an overridable `ELF2HUNK` variable and pin its binary hash before use.

`python3 scripts/check-elf2hunk-padding.py input.elf old.exe fixed.exe` checks
stripped HUNK output against the ELF's allocated section sizes: only trailing
padding may change, every new padding byte must be zero, and all other bytes
including relocation tables must match. Altering a real section byte must fail.
The Prince of Persia 2 game and native installer both pass this check; repeat
conversion and clean-build comparisons are required in the consuming port.
