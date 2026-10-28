# Playbook: porting a game from another platform to the Amiga

For an existing project, read only the section needed for the current task. Use the
[task index](../index.md) for focused references and shared helpers. Read §0 when
starting a new project; follow the complete workflow only when setting one up.

> `$PROJECTS` below is the directory that holds the project checkouts (AmigaXDev's parent) and
> `$ORIGINALS` the directory with the original game files the user supplies. Neither is ever
> written into a repo.

> **For an agent starting a new port from an empty directory and the user's original files.**
> Follow the phases in order. Each ends with a gate; do not commit work of the next phase until
> it passes. Everything here was learned on the ports below. Reuse their harnesses: copy, don't
> rewrite, and read the matching project doc before re-deriving anything.

| Project | Original | Approach | Target |
|---|---|---|---|
| Rescue on Fractalus | Atari 8-bit, 6502 `.xex` + cartridge ROM | Ghidra → 6502 transliterated to C → native C twins → 68000 asm twins | A500, 68000 |
| Revs | BBC Micro, 6502 DFS disc | the same, newer transpiler (self-modifying code as runtime dispatch, MOS intercepts) | A500, 68000 |
| Vette | Macintosh, 68000 CODE resources | original instructions run natively; Toolbox services implemented | A1200 class, 68020 |
| Alone in the Dark | Macintosh, 68020 CODE resources | as Vette, reusing its runtime | AGA, 68020 + Fast RAM |
| Pokeri | arcade board, 68008 EPROMs | original instructions run natively; board devices hooked | 68020, AGA recommended |
| Slicks | DOS 286 executable | routines recovered into native C/C++ and 68020 asm against an x86 oracle | A1200, 68020 |
| Secret Weapons of Luftwaffe | DOS real-mode x86 with overlays | offline x86 → IR → 68020 assembly translator | A1200, 68020 |
| Downwell | Windows GameMaker build | behaviour-first reimplementation from VM bytecode and resources | A500, 68000 |

The display/hardware layer of every port comes from the dA JoRMaS framework (§6). Stunt Car
Racer is an Amiga original rebuilt from its disassembly at 50 FPS; for that kind of work use the
[WHDLoad playbook](new-game-playbook.md), not this one.

Getting to a release means, in order:
1. an executable reference: the original running unattended under an emulator (§4);
2. a complete static map of the original's code and external surface (§5);
3. a port whose correctness is settled by tests against that reference, never by agreement
   with itself (§7–§11);
4. an end-to-end build on the target, profiled before anything is optimised (§10, §12);
5. a WHDLoad installation that takes the user's own data, and an audited archive (§13).

---

## 0. Rules (put these in the new repo's AGENTS.md before anything else)

`AGENTS.md` holds the agent instructions, for Claude Code too; add no `CLAUDE.md`. Keep AGENTS.md
to rules and pointers (every agent rereads it on every turn); hard-won detail goes in `docs/`,
with a row in AGENTS.md's doc table saying when to read it. Its contents, including the path to the
installed shared index, are in [a project's agent instructions](../environment.md#a-projects-agent-instructions).

- **Never commit original or byte-derived material**: binaries, disc and ROM images, resource
  forks, unpacked data, generated disassembly and listings, generated code that embeds original
  tables, screenshots, audio captures, traces, emulator state, saves. Keep them in ignored
  `tmp/`, `ref/`, `data/`, `rom/`, `disasm/` (except `symbols.csv`), `build/`, `extracted/`.
  Inputs without an extension (EPROM dumps: Pokeri) need name rules too; check
  `git status --ignored` before any `git add` of new files. Hashes and names may be committed.
- **The original is the ground truth**, running under its reference emulator. The host build
  and the Amiga build are never compared only with each other or with themselves.
- **Preserve the original's decisions.** Implement the services it calls; do not replace game
  logic with screen-specific guesses. Unknown calls, control flow, code writes, ports, device
  accesses and interrupts are named loud stops until deliberately supported. A fallback or no-op
  is not evidence that a path is safe.
- **Tests settle correctness, not confidence.** A timeout or an unreached probe is never a pass;
  every check needs a positive completion signal, and a negative observation needs a positive
  control proving the path ran.
- **No performance claim without a measurement** from the right instrument on matched
  workloads ([measurement method](../reference/measurement-method.md)).
- **Never `pkill fs-uae` or `pkill gdb`** (nor MAME, DOSBox, jsbeeb): projects share the host.
  The shared `fsuae_common.sh` kills only this directory's recorded pid; reference-emulator
  scripts must record and kill their own pid the same way.
- **No local paths in the repo** (no home directories, usernames, `/tmp`, paths into other
  projects). Name another project by name. Shared files come from the variables of the shared
  `env.sh` (§1); scratch output goes to ignored `tmp/`.
- `docs/open-work.md` is the **only** work queue: open items with acceptance checks, removed in
  the commit that completes them. Measured dead ends stay there so nobody repeats them without a
  changed premise. **History belongs in git**; docs describe the current state.
- Names have one source of truth (`disasm/symbols.csv`), and addresses in docs use the
  original's own numbering (file offset, (segment, offset) for Mac CODE, guest address for 8-bit
  machines), never an Amiga load address. Mark evidence MEASURED, DERIVED or INFERRED.
- Owner decisions (target machine, scope, intentional departures from the original) are listed
  in one table (Alone in the Dark `docs/design.md` §5) and changed only by the owner. Ask at
  genuine decision points; proceed on documented defaults otherwise.
- Commits: the author, signing, hook and trailer conventions the user gives. In these repos:
  `Vesa Halttunen <vesuri@jormas.com>`, unsigned, `core.hooksPath=/dev/null`, no Co-Authored-By
  or other trailers, commit directly to `main`, one verified coherent change per commit. Keep
  remote and authentication overrides repository-local; never change global git settings.
  On creation or a fresh clone, set `git config --local commit.gpgsign false` and
  `git config --local tag.gpgsign false`, then verify both effective values. Tag signing
  is independent of commit signing and may otherwise inherit work defaults.
- Do not edit a shell launcher while it runs (bash resumes reading at a stale offset).

## 1. Host prerequisites (installed by AmigaXDev)

`make setup` in AmigaXDev installs the toolchain, FS-UAE builds, Kickstarts, WHDLoad, the
Developer CD and the Python environment (README and [environment](../environment.md)); the
port-specific tools come from `Brewfile.extras`. `make check` verifies them.

| What | For |
|---|---|
| m68k-amiga-elf gcc/g++/gdb/objdump, vasm, `elf2hunk` | the Amiga build ([port toolchain](../reference/port-toolchain.md)) |
| FS-UAE x86_64 with the gdb stub, arm64 (`FSUAE_ARM`), arm64 aprof (`FSUAE_APROF`) | running, debugging and profiling ([headless FS-UAE](../reference/headless-fsuae.md)) |
| Kickstarts (`KICKSTART`, `KICKSTART_A1200`, `KICK13` + `RTB`), `SETPATCH`, `WORKBENCH_ADF` | boot and the KickEmu slave |
| WHDLoad (`WHDLOAD`; 20.1 in `WHDLoad/`), `INSTALLER43`, `LHA` | slave, installer test, release archive |
| `ADCD`, `AGA_GUIDE` | Hardware Reference Manual, RKMs, autodocs, AGA registers |
| Ghidra (`~/.local/share/ghidra`), openjdk@21 | headless static analysis (§5) |
| MAME, DOSBox-X, DOSBox Staging, atari800, volta (jsbeeb) | reference emulators (§4) |
| Unicorn (`AMIGA_UNICORN`, patched for arm64), capstone | host-side x86/68k oracles and decoders |
| hfsutils, unar/lsar, lhasa, 7zz, ffmpeg, amitools (`xdftool`) | extracting originals, decoding captures (§3) |
| Python 3.12 + Pillow, numpy, capstone, amitools | the tools; first on `PATH` after the shared `env.sh` |
| SDL2 (`sdl2-compat`, `sdl2_image`), libsndfile | the host build (§8) |

The project's `amiga/env.sh` sources the shared file and sets only what differs:

```sh
#!/usr/bin/env bash
# project values that differ from the shared defaults go before the source line
. "${AMIGA_ENV:-$HOME/.local/share/amiga/env.sh}"
```

Source it in the same shell command as the build or run (`cd amiga && . ./env.sh && make`).
Python tools read the same variables with the same defaults; Makefiles use `?=`. Never fall back
to copies elsewhere on the machine. A tool the shared environment lacks (Downwell's
UndertaleModTool, for one) is pinned by version and sha256 in the project's own
bootstrap script and installed under ignored `tools/vendor/`.

Gate: `make check` in AmigaXDev passes; `m68k-amiga-elf-gcc --version` works after `. amiga/env.sh`.

## 2. Identify the original and choose the approach

Record before writing code (in `docs/source-inventory.md` and the README's checksums):

- exact files, sizes and SHA-256 of what the user supplied, and which version or release it is
  (variants differ: Rescue on Fractalus's v5.0 cartridge is the console version, 4.1 the
  computer one; adopt the other version's fixes, not its behaviour);
- the original CPU, machine and OS/firmware services the program uses;
- the packer or loader between the file and the running program (Slicks' Compack, Revs'
  self-relocating loader and second unpack, a Mac far-model CODE 0/CODE 1 loader);
- the reference emulator that runs it and its configuration (§4).

Then choose, with the owner, the **target** (A500 68000 with uniformly slow memory, or A1200
68020/AGA) and the **approach**. The original's CPU decides the approach and the project to
start from:

| Original | Approach | Start from |
|---|---|---|
| 68000-family (Mac, 68k arcade/board, ST) | run the original instructions natively: relocate, hook OS traps and device accesses, implement the services | Vette (Mac runtime; Alone in the Dark reused it), Pokeri (board devices, Musashi host model) |
| 6502 (Atari 8-bit, BBC, C64) | Ghidra listing → transliterated C with a 6502 memory image → native C twins validated against the transliteration → 68000 asm twins | Revs (newer transpiler), Rescue on Fractalus (its postmortem) |
| x86 DOS | offline translation to 68020 assembly, or routine-by-routine recovery into native code, both oracle-tested against x86 | Secret Weapons of Luftwaffe (translator), Slicks (recovery, PC reference loop) |
| bytecode / engine data (GameMaker and similar) | lossless extraction → auditable IR → portable deterministic core → Amiga backend | Downwell |

Write the faithfulness-seam rule (which code is a validated faithful twin and which is
Amiga-only and lossy) as the first architecture doc, before the first twin (Revs
`docs/faithfulness-seam.md`; Rescue on Fractalus postmortem §5).

Gate: `make inspect` (or equivalent) reproduces the recorded hashes and headers from the local
originals; target and approach are in the owner-decision table.

## 3. Extract the original data

Keep the user's files untouched (`data/` or `ref/`, read-only); work on copies in `tmp/`. Every
generated manifest records the extraction tool's version and the input hashes.

| Container | Tool | Notes |
|---|---|---|
| classic Mac HFS volume | `hmount`/`hcopy -m`/`humount` (hfsutils) | keep both forks (MacBinary); `python3 -m amigaxdev.mac.hfs_extract`, `amigaxdev.mac.macbin`, `amigaxdev.mac.resource_fork` |
| NDIF/StuffIt archive | `unar`; Vette `tools/ndif2raw.py` | both forks again |
| PC archives (7-Zip, ZIP) | `7zz`, `unar` | |
| `.lha`, `.lzx` | `lha` (lhasa), `unar` | |
| ADF | `xdftool` (amitools) | |
| BBC DFS `.ssd` | Revs `tools/ssd_load.py` | the composed image is a reconstruction until the reference dump agrees (§4) |
| Atari `.xex` | Rescue on Fractalus `tools/` (segment table) | |
| EPROM set | Pokeri `tools/roms.py` (`make roms SRC=…`) | verify each chip's hash, then unpack |
| GameMaker `data.win` | UndertaleModTool CLI (Downwell `tools/bootstrap-utmt.sh`) | VM assembly and resource metadata outrank decompiled GML |

A packed executable is not trusted until its post-unpack image and entry state have been captured
from the reference and reproduced independently from the file and the unpacker's semantics
(Slicks: DOSBox Staging dump at the decoder's far `JMP`, normalised and `cmp`'d against a Unicorn
unpack).

Gate: extraction is a make target; rerunning it reproduces identical hashes.

## 4. Build the reference loop first

Rescue on Fractalus's postmortem: the reference-capture loop and the target measurement loop
"diagnosed timing and render bugs precisely where static reasoning kept failing", but were built
reactively. Build both before the port needs them.

| Platform | Reference | Example |
|---|---|---|
| Macintosh | MAME (`mac2fdhd`, `mdc48`), Lua autoboot/input scripts | Vette `docs/mac-reference-loop.md`, `tools/mame_mac_input.lua` |
| DOS | DOSBox-X (286 core, instrumented with patches), DOSBox Staging as a second CPU personality | Slicks `tools/patches/`, Secret Weapons of Luftwaffe `docs/pc-reference-loop.md` |
| BBC Micro | jsbeeb, headless under Node | Revs `docs/bbc-reference-loop.md`, `tools/bbc_*.mjs` |
| Atari 8-bit | atari800 in FIFO mode | Rescue on Fractalus `tools/extract_a8s_ram.py` |
| arcade board | Musashi host harness with device models | Pokeri `host/` |
| Windows | the original build plus its VM bytecode | Downwell `docs/method.md` |

What the loop must do:

- run headless and unattended from a **disposable copy** of the originals, with fixed input and
  RNG, a time limit and explicit config/NVRAM directories (MAME needs `SDL_VIDEODRIVER=dummy`,
  `-window`, `-cfg_directory`, `-nvram_directory`; `-video none` alone still opens a window);
- stop with a distinct reason (success, limit, unsupported event, guest failure) and report
  success only from guest state at a named milestone;
- dump memory, registers and frames at named milestones, and trace executed addresses, edges,
  interrupts, port and device I/O, writes to code, and file operations, normalised to the load
  base, armed by a proven guest event;
- drive input deterministically (DOSBox-X `autotype`, MAME Lua, jsbeeb key scripts).

First job: dump RAM at the program's entry and diff it against your extracted image. Until that
diff is clean, every address derived from the image is provisional. Gate on stable crops and
state, not full frames, once the simulation runs: AI and timers drift between runs. More in
[validation harness](../reference/validation-harness.md).

Gate: one command boots the original, reaches a named state and writes a reproducible capture.

## 5. Map the original statically and live

Ghidra runs headless from make targets (`make ghidra`, `make map`), started from the project root
with `-scriptPath "ghidra_scripts;$AMIGA_GHIDRA_SCRIPTS"`. AmigaXDev ships the scripts that are
the same for every port: `ExportListing.java` (writes the listing the generators read; Slicks and
Secret Weapons of Luftwaffe use `ExportAuditListing.java`), `DumpCallGraph.java`,
`DumpZeroPage.java`, and for 68000 Mac originals `MacMarkEntries.java` (seeds
`ghidra_scripts/entrypoints.csv`), `MacApplyNames.java` and `MacDumpTraps.java`. The project's
`ghidra_scripts/` keeps what is tied to its original CPU or machine: a `MarkEntries.java` that
seeds `entrypoints.csv`, an `ApplyNames.java` that applies `disasm/symbols.csv`, and a surface dump
such as `DumpHwAccesses.java` for memory-mapped hardware. `tools/ghidra` links the shared install.

- **Seed every entry point before generating anything** (the postmortem's highest-leverage
  finding): every computed jump, jump table and RTS-dispatch idiom, all hardware and OS vectors
  and shadow vectors, interrupt, callback and trap targets, plus the targets the live trace
  observed. Add a newly found indirect target to `entrypoints.csv` the moment it is identified;
  Ghidra cannot reach it by flow (Revs `docs/entrypoint-sweep.md`).
- Spend one concentrated pass giving rough behavioural names before deep work; record names that
  turn out wrong in `docs/rename.md` with an address and how to settle it, and rename in
  `symbols.csv`, never in generated files.
- Inventory the **external surface**: every OS/firmware call, trap, port, device register,
  display memory access, executable write, overlay and self-modifying site (Slicks
  `docs/external-surface.md`, Vette `docs/static-map.md`). This is the list of services the port
  must implement.
- Classify every byte as code, data, padding or unresolved; an executed byte must never be
  unclassified.
- **Disassemble the image that executes, not the file.** Prove the runtime image with two
  independent captures (§3); Slicks' packer and Revs' self-relocation both made the file image
  wrong where it mattered.
- **One address convention, never mixed**: Mac `(segment, offset)`; DOS normalised to load
  segment 0 with the relocations reversed (Slicks); `(overlay, segment, offset)` when overlays
  exist (Secret Weapons of Luftwaffe).
- **Never classify mixed code and data by linear sweep.** A linear sweep of an overlay invents
  hundreds of plausible instructions from ASCII (Secret Weapons of Luftwaffe; Vette rejects it).
- **Static analysis is an upper bound, the trace a lower bound**: combine them, and check every
  live surface site against the static map (Vette). A body no scenario drives is unproven, not
  dead.
- **The map is done when no referenced address is undecoded** and the residue is counted and
  reported (Revs accepted 685 bytes explicitly). A coverage number that improves because the
  tool got looser is worse than none: Revs reverted a widened pointer lookback that fabricated
  targets.
- **Code at an address can be different code at another time**: overlays, runtime-built pages
  (Revs). Key translated code by resident image, not by address alone.
- **Report every orphan run and nested call;** never infer function membership from
  fall-through. Revs dropped code that ended in a terminator and turned a call into a goto.
- **Classify every code write mechanically** (operand, opcode, branch, call, extent: Revs had 59
  sites in five classes) and prove the absence of writes to executed bytes by a byte-level trace
  check per path (Slicks). A patched call or jump target set is explicit and checked at
  generation time.

Gate: static and live evidence agree on the executable surface (a check target, e.g. Vette
`make static-map-check`); generation does not silently treat unknown targets as data.

## 6. Scaffold the repo

Layout, as the ports converged on it:

```text
AGENTS.md  README.md  VERSION  Makefile                host build, generation, tests, dist
docs/                 open-work.md, design/architecture (with owner decisions), toolchain,
                      reference loop, static map, faithfulness seam, testing, performance, release
src/                  game core, generated code (src/gen/, regenerated, never hand-edited)
src/platform/host|sdl/  host backend
src/platform/amiga/   Amiga backend; framework/ (vendored dA JoRMaS subset + UPSTREAM.md)
amiga/                Makefile, env.sh, run.sh, debug.sh, diag_run.sh, *.gdb probes
ghidra_scripts/       the CPU-specific scripts above + entrypoints.csv
disasm/symbols.csv    names (the rest of disasm/ is ignored)
tools/                reference drivers, extraction, generators, oracles, packaging; _amigaxdev.py
whdload/              slave source and Makefile; smoke_name.i for the shared smoke slave
release/              Install, ReadMe, icons as base64 text
tmp/ ref/ data/ build/  ignored
```

Copy from the project chosen in §2, then strip its game: `$PROJECTS/<that project>/`
`.gitignore` (adapt the originals' names and extensions), `Makefile` and `amiga/Makefile`,
`amiga/env.sh`, `run.sh`, `debug.sh`, `diag_run.sh` and `ghidra_scripts/`. Take the framework
from AmigaXDev's canonical tree (`$AMIGA_FRAMEWORK`) into `src/platform/amiga/framework/`, and the
shared Python tools (release, Mac and DOS helpers, disassembly) from the `amigaxdev` package
rather than from another port's `tools/` (AmigaXDev `docs/environment.md`, "Shared tools").

**The dA JoRMaS framework.** `AmigaHardware` (takeover, interrupts, blitter queue), `Bitmap`,
`CopperList`, `Palette`/`Palette24Bit`, `Sprite`, `Util`, with `SASCCompat.h` and
`compat-include/` for the `-nostdlib` GCC build. Each `.cpp` has a portable C++ body and an
`ASSEMBLER` variant backed by `*Assembler.s` (`NO_ASSEMBLER=1` selects the portable bodies). The
dual SAS/C + GCC guide is dA JoRMaS `Template/C++/GCC-PORT.md`. Ports vendor only the subset
they use and replace `Production`/`Part`/`ProductionRunner` with a plain `main()` + VBI server
loop. The canonical tree uses the neutral `DAJ_`/`daj_` prefixes and carries both lineages
(the full asm set of Revs, Vette and Alone in the Dark; the AGA `Palette24Bit` variant of Slicks
and Secret Weapons of Luftwaffe) with the measured AGA FMODE 3 fetch values. Record the AmigaXDev
commit, the classes taken and every local change in `UPSTREAM.md` (Slicks and Secret Weapons of
Luftwaffe keep this in `framework/README.md`). `python3 -m amigaxdev.framework diff PROJECT`
shows what differs from the canonical tree, and `sync` copies canonical files in under the
port's prefixes; a fix made in a port goes back to AmigaXDev `share/framework/`.

Gate: `make` builds an empty host program and `cd amiga && . ./env.sh && make` an empty Amiga
executable that `./run.sh` boots and quits cleanly.

## 7. The port core, by approach

### Rules for any generator or translator (transpiled 6502, translated x86)

Slicks planned an x86 → IR → 68020 translator and shipped without one: its rules banned the
emulation failure mode (generated C, a CPU struct, a dispatcher) but not hand-porting, the
translated-skeleton gate could be ticked from hand-written code, and hand work gave visible
pixels per hour while the translator gave none for days. Every hand routine passed its oracle,
so every step looked right. The guardrails Secret Weapons of Luftwaffe adopted from that
(`docs/translation-lessons.md`), in generic form:

| Guardrail | Enforced by |
|---|---|
| Guest routines exist only as generator output, with a generator/annotation hash header, never edited | a build check of the headers; regeneration is byte-identical |
| Hand-written code is the runtime only (OS/BIOS services, device models, overlay loader, interrupt delivery, display, audio, input), named by surface item, never by guest address | a lint: no guest-address-named symbol outside generated code |
| Native replacements of guest routines are an explicit table (guest range, reason, oracle), empty by default; callers of a replaced leaf stay generated | `make gen` prints the table and its count (Revs keeps `MANUAL_FUNCS` empty) |
| A wrong result is fixed in the IR semantics, lowering or annotations, then regenerated | the hash check |
| Phases are hard gates: instruction differential green before block lowering, block lowering green before game code links on the target; no target milestone counts unless its pixels come from generated code | phase exit criteria name generated-code coverage, not pictures |
| Generation reports coverage against the reference trace: executed guest instructions translated, interpreted, replaced or untranslated | the report fails on executed-but-unclassified bytes |
| The first visible output comes early **from the translator**: a small, self-contained traced subgraph on the target in the first days | the first vertical slice is planned around generator output |
| No captured frames, invented behaviour or speculative names in shipped code; names carry an evidence class | review; Vette's `symbols.csv` evidence column |

- **Standing rules name both failure modes you expect**: emulation and hand-porting.
- **Make the generator's output good before mass generation**; one generator fix upgrades the
  whole corpus (Rescue on Fractalus postmortem, Revs).
- **Generation fails rather than emitting a plausible stub** for an unknown OS call, an
  annotation that is not an instruction start or an unresolvable target.
- **Loops spanning a mid-function entry stay branches.** Splitting at entries turned loops into
  mutual recursion and stack growth in Revs' C. A guest jump is a branch and a guest call a call;
  never conflate them.
- **Replace device-bound routines, not device ports one by one**: Slicks saw 10.3 M port
  operations and 1.36 M VGA writes from 16 sites, which per-port emulation cannot translate ahead
  of time. Every such seam has an explicit register, flag and memory contract in both directions.
- **The original's timer interrupt is asynchronous state, not a call** (Slicks' INT 08h ran from
  game code and during DOS services); deliver interrupts at safe guest boundaries.
- **Spin-waits:** a wait on an I/O port is a device-model gap; a wait on RAM is a hook candidate.
  Report the candidates and hook only waits that own a frame (Revs hooked 1 of 41).

### Original 68k instructions run natively (Vette, Alone in the Dark, Pokeri)

- Load and relocate the original yourself; check sizes, fingerprints and the original bytes
  before every patch. Never map the original's low memory (Mac Page 0, a board's vectors) over
  Amiga vectors or Exec state: redirect those operands to a private shadow.
- Replace each device access or OS trap with a hook (Line-A for Mac traps; checked Line-A hooks
  and relocation descriptors for board I/O) that preserves every live register and condition code
  the callers read. Tables come from runtime coverage audits, not from Ghidra alone.
- Run the original in user mode on a private stack; never call original code from an Amiga
  interrupt. The VBI updates time, input and Paula; the game's handlers and callbacks run at safe
  user-mode boundaries. OS file operations open a bounded system window and retake the machine.
- Measure the system stack your trap helpers leave (Alone in the Dark: 6 KiB under FS-UAE;
  a 32-byte margin corrupted Exec during VBI with otherwise correct output).
- Crash diagnosis and hook-coverage regressions: [native port validation](../native-port-validation.md).

### 6502 transliterated to C (Rescue on Fractalus, Revs)

- The transpiler reads the Ghidra listing and `symbols.csv` and emits C over a byte-exact
  little-endian `mem[]`. Make it emit clean C (liveness-gated flag elision, named memory from
  `symbols.csv`, folded load/store idioms) **before** mass-generating; every regen pays for it.
- A native twin keeps the transliteration as its oracle (`VALIDATE_FUNCS`: the transliteration
  is emitted under a suffix and the plain name links the native version). Typed computation in
  the core, ABI state reconstructed at the seam; a shim reproduces every register and flag its
  callers read.
- Self-modifying code becomes runtime dispatch; patch bytes are evaluated per context (Revs:
  per circuit), never as a union of legal bytes.
- `mem[]` is little-endian and the Amiga big-endian: no wide-pointer aliasing; enforce it with a
  lint (`make endian-lint`).
- Rescue on Fractalus `docs/postmortem.md` is the checklist; Revs `docs/transpiler.md` and
  `docs/native-maintenance.md` the current practice.

### x86 translated or recovered (Secret Weapons of Luftwaffe, Slicks)

- Pass the phase gates in order (Slicks `docs/phases.md`, Secret Weapons of Luftwaffe
  `docs/phases.md`): reference loop and proved runtime image → static/live map → x86 semantics
  differential-tested against Unicorn → 68020 backend tested on a host 68k core → an end-to-end
  vertical slice on the A1200 model **before** completing or optimising.
- No generated-C CPU emulation: guest registers stay in native registers, flags virtual, direct
  guest edges become direct native branches, full x86 state only at demonstrated boundaries.
- Guest code reaches the Amiga only as translator output; fix the translator or its annotations
  and regenerate, never the output. A native replacement of a guest routine is an HLE table entry
  with a reason and an oracle.
- Slicks shows the fallback when a full translator is out of scope: recover each routine into
  native C/C++ or hand-written 68020 assembly, each one checked against the original x86 code
  under an independent oracle.

### Behaviour-first reimplementation (Downwell)

- Lossless view (bytecode, resource order and IDs, event bindings) beside a readable view
  (decompiled source or AST), every node traceable to the lossless one. Neither generated code
  nor decompiled source becomes the only truth.
- Game logic in `src/core` with no platform dependencies; deterministic fixed ticks, seeded RNG,
  recorded input edges and compact state digests.

## 8. The host build

The host build is a proof and differential platform, never the fidelity or performance ground
truth. What it is depends on the approach: a playable SDL backend (Rescue on Fractalus,
Pokeri, Downwell), a deliberately headless engine for differentials and algebra proofs (Revs),
or a Unicorn 68020 run of the generated program (Secret Weapons of Luftwaffe). Mac ports that run
the original natively have host unit tests only.

- Keep platform code behind a small interface (`platform.h`); host conveniences must not leak into
  game state or simulation semantics.
- Run each differential big-endian as well as on the little-endian host, or lint every wide alias
  of guest memory, so endianness cannot hide behind a green host run.
- Host proofs of Amiga-only code (Rescue on Fractalus `make hostproof`) hold a verbatim snapshot
  of the routine: green means the transformation is sound, not that the shipping source still
  matches.

## 9. The Amiga platform layer

Read [Amiga hardware](../reference/amiga-hardware.md) first. The rules every port converged on:

- One owner of the display registers (`VetteScreen`, `AitdScreen`): publish complete copper lists
  and bitplane/sprite pointers **first** in the VBI, before input or audio, never mid-frame.
- Present completed frames, not individual drawing calls; pace them globally (Alone in the Dark
  D3). Keep explicit dirty rectangles; no shadow-framebuffer or tile-diff machinery.
- On AGA, design the screen for 64-bit bitplane fetch (`FMODE` = 3) from the start: 8-byte aligned
  bitplanes, a width that is a multiple of 64 pixels, and an FMODE 0 path for OCS/ECS. It frees
  three quarters of the display's Chip-bus slots; see [the Chip bus](../reference/amiga-hardware.md#the-chip-bus).
- Translate the original sound chip to Paula (POKEY, AY-3-8912, Mac sound drivers, AdLib FM);
  Rescue on Fractalus `docs/sfx-events.md` and Pokeri `PaulaAy.cpp` are the prior art.
- Load the user's original data through DOS before taking over the machine, validate it, and fail
  with DOS error 20 before takeover if it is wrong; restore everything on a normal quit.
- A software mouse pointer becomes a sprite without touching guest code: at each present, if
  the guest's pointer is complete in its framebuffer, mask it with the guest's own save buffer
  and describe it for the sprite; change visibility only on a state held for a field (the
  guest's hide-move-show must not flicker); lead the position at the VBI by the guest's own
  motion rule, checked at every tracker exit; validate shown planes + decoded sprite words
  against the reference frame (SWOTL `docs/pointer-plan.md`).
- A `__chip` static initialiser is silently discarded (`.MEMF_CHIP` is a BSS hunk): fill chip
  data at runtime.
- Simulation timing that must survive a faster renderer: [fixed-time simulation](fixed-time-simulation.md)
  and [simulation and presentation](simulation-and-presentation.md).

## 10. First Amiga boot under FS-UAE

```sh
cd amiga && . ./env.sh && make
./run.sh            # windowed, with sound; left mouse button or the game's quit
./debug.sh          # gdb stub + m68k-amiga-elf-gdb, source level
./diag_run.sh 60    # headless: run, then the read-only prints of a .gdb script
```

The launchers build their options with the shared `fsuae_options` and start through
`fsuae_launch`/`fsuae_exec`; debug and warp runs are silent and behind the other windows
(`SOUND`, `WINDOW=front|back|none`, `EXTRA_ARGS` override). Details, the probe pattern and the
pitfalls: [headless FS-UAE](../reference/headless-fsuae.md); flags, audits and link layout:
[port toolchain](../reference/port-toolchain.md). The traps every port hit:

- `make clean` after changing build flags, `PROBES`, or a widely included header: the Makefiles
  do not track them, and a partial rebuild links a working-but-wrong binary.
- Every global a `.gdb` script reads must be kept by the linker (`PROBE_SYMS`); a collected symbol
  resolves into instruction bytes. A `.gdb` script aborts at the first unknown symbol.
- The gdb stub serves reads and drops writes: inject test input from C (a `-D` flag and a VBI
  window), and keep `.gdb` scripts read-only.
- Check that `.run/gdb-out.log` belongs to the current run and build before reading numbers.
- No spaces anywhere on the build path (the LTO link spawns a path-encoded wrapper).

Gate: the port reaches a named game state on the target model headlessly, proven by a probe, and
`run.sh` shows it.

## 11. Faithfulness and validation

[Validation harness](../reference/validation-harness.md) holds the method. The rules to put in
the repo from the first twin:

- **Fixture or fail**: a validated function with no fixture fails; a zero-count check is a
  failure. Randomise inputs including the gating bytes.
- Make exit registers and flags consumed by callers part of the contract, not an "incidental"
  difference.
- Measure target-only code with an **in-process differential** against its C oracle (same run,
  same inputs), never a cross-run picture: a faster renderer changes the trajectory.
- Before trusting a new gate, plant a few deliberate defects, confirm it fails, then remove them
  (a make target such as Secret Weapons of Luftwaffe's `make test-sabotage`).
- A change to the transpiler, CPU model or memory representation changes the oracle too: record
  determinism baselines first, never re-record one to make a failure pass.
- Know what each check answers: installation, execution and the resulting picture are separate
  questions (Revs `tracks`, `track-run`, `viewdiff`).
- Validate in proportion to the change:

| Change | Evidence |
|---|---|
| pure helper | host checks with boundary and rejection cases |
| loader or binary hook | original-byte guards, register/CCR preservation, bounded native completion |
| new service | original arguments and results, native call-site acceptance |
| display / audio | matching game state, full viewport or event/voice contracts on the target |
| performance | matched scenario in guest ticks or fields, pinned CPU model, profiling overhead stated |
| installer / release | extraction hashes, real Installer run, WHDLoad execution, independent archive check |

## 12. Profiling and optimisation

- **Profile an end-to-end skeleton on the target before choosing what to optimise** or promising
  a frame rate. Rescue on Fractalus declared an "algorithmic floor" that hand assembly later
  disproved: the ceiling was the compiler.
- Quote milliseconds per frame from matched, deterministic workloads (fixed RNG, fixed input),
  keeping gameplay, front-end and transition windows apart; displayed PAL FPS is quantised to
  `50/N`. Rebuild and remeasure the baseline in the same session and quote the A/B, not absolutes
  from old notes.
- Name the work a change removes and estimate the saving from the profile before writing it;
  afterwards measure the same workload, including its worst frame. Correctness tests and new
  infrastructure are not performance wins.
- Fail experiments cheaply: quick smoke and benchmark against the parent first; full fidelity
  gates only for the promising ones (Slicks).
- Clean up the C before writing assembly; keep the portable C as the oracle of every asm twin,
  behind a switch (`make <NAME>_C=1`).
- On a 68000 target: reduce memory accesses (there is no cheaper memory on an A500), never emit a
  32-bit software multiply or divide (link audit), align even-sized globals to 4 for the 68020
  (ELF audit). [68000 optimisation](../reference/m68k-optimisation.md),
  [measurement method](../reference/measurement-method.md).
- ISR work has its own budget and hides inside whatever phase it interrupted.

## 13. WHDLoad slave and release

A port needs the OS, so its slave is a KickEmu slave (`kick13.s` for a Kickstart 1.3 target,
`kick31.s` + `kickfs.s` for 3.1) that mounts `data` and `LoadSeg`s the executable; Rescue on
Fractalus `docs/whdload-slave.md` §0 explains why a plain loader is not enough. The slave builds
on the Mac with vasm against `$WHDLOAD`; a smoke slave (AmigaXDev `whdload/SmokeSlave.s`,
assembled with `-I.` and the project's `whdload/smoke_name.i`) tests the harness without a game.

- Size chip/expansion memory and the stack from measurements, not guesses (Rescue on Fractalus
  §2); set `WHDLF_EmulLineA` when the original uses Line-A (Mac ports).
- The user supplies the original data; the installer copies and validates it (exact size and
  SHA-256 per file, or a bundled helper extracting an allowlist from the user's archive) into a
  staging drawer, and replaces `data/` only on success. Reuse/replace and save preservation:
  [native port validation](../native-port-validation.md).
- `make dist` does a clean release build (no probes, profiling, self-tests or diagnostic markers;
  `elf2hunk -s`), the slave, the helper, then a packager with an explicit file allowlist that
  refuses any member matching an original's hash (Revs also scans for any 256-byte block of the
  original engine), then an independent checker. Version and date come from `VERSION` and must
  match in the executable, slave, installer and ReadMe.
- Archive with `amigaxdev.release` (the shared `LHA`, LH5, members in the given order, a fixed
  DOS stamp, the installer and drawer icons, refusal of originals and of an existing archive);
  the project's `package_release.py` keeps only its file map. Verify each member with Lhasa. Converged package layout, icons, ReadMe sections, Installer 43 script rules and the
  Installer test traps: Secret Weapons of Luftwaffe `docs/release.md`; the WHDLoad playbook
  [§13](new-game-playbook.md#13-release-archives) for archive mechanics.
- Hardware-only failures: [hardware debugging](new-game-playbook-hardware.md) and
  [MMU compatibility](whdload-mmu.md).

Copy from a released port: `$PROJECTS/Pokeri/` `release/Install`, `release/ReadMe`,
`release/icons/`, `tools/package_release.py`, `tools/_amigaxdev.py`, `tools/check_release.py`,
`tools/test_release_installer.py`, `tools/test_whdload.py`, `whdload/Makefile` and
`whdload/smoke_name.i` (Pokeri's Installer script is the newest); Slicks for a bundled
extraction helper; Vette for Mac-fork extraction.

## 14. Definition of done

**Ready to port** (end of §6):
- [ ] AGENTS.md rules, doc table and shared index path (no CLAUDE.md), `.gitignore` guarding every original name and extension.
- [ ] Owner-decision table: target machine, approach, scope.
- [ ] Originals hashed; extraction reproducible.
- [ ] Reference loop reaches a named state headlessly with a positive completion signal; the entry
      dump agrees with the extracted image.
- [ ] Entry points seeded exhaustively; external surface inventoried; static/live check passes.
- [ ] Faithfulness-seam rule written.
- [ ] Empty host and Amiga builds; `run.sh` boots and quits.

**First light** (end of §10):
- [ ] An end-to-end path runs on the target model from the port's own code and reaches a
      reference milestone, checked by a probe.
- [ ] Validation harness fails on a missing fixture and on planted defects.
- [ ] A skeleton profile on the target says where the frame time goes.

**Release** (end of §13):
- [ ] Every open-work item closed or explicitly deferred by the owner.
- [ ] Fidelity gates green on the release build; performance quoted from matched workloads.
- [ ] Two clean builds produce identical stripped executables.
- [ ] Installer tested with real Installer 43 (fresh, reuse, replace, incomplete data, saves).
- [ ] WHDLoad and standalone runs on the stock target, PRELOAD on and off.
- [ ] Archive audited independently; size and SHA-256 recorded; publishing reported separately
      from building.
