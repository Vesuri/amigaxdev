# Find guidance for your task

Read the project's own instructions and current task first. Choose a row below, then
read the relevant headings rather than loading every linked document. These are lookup
references, not a mandatory reading list. Search headings with `rg -n '^##' FILE` and
search for the affected option, helper or symptom before reading surrounding text.

## Workflows

| Task | Start here |
|---|---|
| Install or update the shared environment | AmigaXDev's `README.md`; [environment variables and project integration](environment.md) |
| Start a standalone WHDLoad improvement | [WHDLoad playbook](playbooks/new-game-playbook.md) |
| Work in a JOTD or StingRay fork | [JOTD](playbooks/new-game-playbook-jotd.md) or [StingRay](playbooks/new-game-playbook-stingray.md); choose one |
| Port a game from another platform | [Porting playbook](playbooks/new-port-playbook.md); choose the matching original CPU/runtime approach |
| Write or repair a project's `AGENTS.md` | [A project's agent instructions](environment.md#a-projects-agent-instructions) |
| Work on AmigaXDev's pending improvements | [Open work](open-work.md); proposals there are not installed capabilities |

## Symptoms and decisions

| Need | Read |
|---|---|
| Find a slave's source, or rebuild a shipped slave that does not come out byte-identical | [Identify the slave](playbooks/new-game-playbook.md#2-unpack-and-identify-the-game): sources, reconstruction, assembler and KickEmu differences |
| Machine preset, CPU, RAM, ROM or MMU settings | [Named setups](reference/headless-fsuae.md#named-machine-setups) |
| Emulator choice, debugger input, bounded field advancement | [Builds](reference/headless-fsuae.md#which-fs-uae), [harness commands](reference/headless-fsuae.md#harness-commands-native-builds) |
| Window placement, sound or screenshots | [Window options](reference/headless-fsuae.md#sound-window-screenshots) |
| Debugger RAM differs from CPU reads; stale flags | [Cache observer](reference/cache-observer.md), [register observer](reference/register-observer.md) |
| Hardware-only crash, black screen, executable cache publication | [WHDLoad hardware debugging](playbooks/new-game-playbook-hardware.md); [native port regressions](native-port-validation.md) for relocated or [self-modifying](native-port-validation.md#self-modifying-original-code) original code |
| WHDLoad MMU faults or vector ownership | [MMU diagnosis](playbooks/whdload-mmu.md) |
| Profile, compare performance or diagnose loading stalls | [Measurement method](reference/measurement-method.md), especially instruments, clock resolution and A/B discipline |
| Instruction/call profiles or native service costs | [Profile reader](reference/measurement-method.md#shared-instruction-profile-reader), [native-service scopes](reference/measurement-method.md#explicit-native-service-scopes) |
| Prove equivalence, construct fixtures or validate gameplay | [Validation harness](reference/validation-harness.md); choose routine, whole-program or user-route checks |
| Change simulation speed, timestep, input sampling or replay | [Fixed-time simulation](playbooks/fixed-time-simulation.md) |
| Smooth rendering without advancing gameplay; projection or animation | [Simulation and presentation](playbooks/simulation-and-presentation.md) |
| CPU instruction costs, C/assembly optimisation or copies | [m68k optimisation](reference/m68k-optimisation.md) |
| Chip bus, copper, blitter, Paula, DMA, interrupts or OS handback | [Amiga hardware](reference/amiga-hardware.md) |
| Macintosh pointer truncation above 16 MB | [Logical and native addresses](native-port-validation.md#macintosh-logical-addresses-and-native-high-pointers) |
| Compiler flags, linking, HUNK conversion or release builds | [Port toolchain](reference/port-toolchain.md) |
| Installer, icons, archives or release validation | [Native port release checks](native-port-validation.md); the selected WHDLoad playbook's §13 for slave releases |

## Reuse before implementing

| Component | Entry point |
|---|---|
| Shell launchers and Python tools (`amigaxdev`) | [Shared tools](environment.md#shared-tools); source in `share/fsuae_common.sh` and `share/pylib/amigaxdev/` |
| Macintosh memory, QuickDraw, resources, clocks and audio | [Runtime helper index](../share/mac-runtime/README.md) |
| Display/hardware framework and deliberate vendor updates | [Framework](../share/framework/README.md) |
| Rectangle chunky-to-planar conversion | [Kalms adapter](../share/kalms-c2p/README.md) |
| Native StuffIt extraction and installation | [Install-data helpers](../share/install-data/README.md) |

For implementation changes, inspect the selected source and its `scripts/test_*`
checks; a helper's presence does not prove that a consumer uses it or that an installed
emulator includes a patch. Verify the selected build and capabilities before relying on them.

## Keeping this guide useful

Keep always-read project instructions to rules, current constraints and a pointer to
this index. Store detailed contracts once, next to their topic, with descriptive headings.
Link from workflows rather than repeating the contract. Preserve useful evidence and
limits, but put run diaries, current checkpoints and project-specific plans in the project.
