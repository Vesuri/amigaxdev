# The framework: the canonical copy

The display and hardware layer (the dA JoRMaS framework) a port vendors (`src/platform/amiga/framework/`), kept here so
fixes have one place to land. Installed as `$AMIGA_FRAMEWORK` (`~/.local/share/amiga/framework`).
Ports keep their own vendored copy and its byte-identical builds; they compare against this tree
and take changes deliberately, with their own measurements:

    python3 -m amigaxdev.framework diff PROJECT [--template DIR]
    python3 -m amigaxdev.framework diff PROJECT AmigaHardware.cpp
    python3 -m amigaxdev.framework sync PROJECT CopperList.cpp CopperList.h

`diff` maps each port's renamed identifiers (`GAME_SASC_ALIAS`, `game_mulu16`, ...) to the neutral
`DAJ_`/`daj_` used here. `--template` names the copy both sides started from; a file that differs
is then classified by which side still matches it. Record the AmigaXDev commit a port's copy is based on in its `UPSTREAM.md`.

## What this copy is

Contents:

- `AmigaHardware`, `Bitmap`, `CopperList`, `Palette`, `Sprite`, `Util`, with the GCC marshalling
  bridges to the `*Assembler.s` routines (`ASSEMBLER` is defined for GCC by `Util.h`;
  `-DNO_ASSEMBLER` selects the C++ bodies). The asm's dotted local labels are sanitised for vasm;
  assemble with `vasmm68k_mot -m68010 -Felf -x -no-opt -nowarn=62`.
- `setPlayfield()` writes LACE, derives the display window and the hires fetch window
  from its arguments and always writes `DIWHIGH`; `isLongFrame()` is the C++ body on both compilers
  (its asm bridge had no routine behind it).
- `Bitmap` takes `interleaved` as in the template. The asm has no non-interleaved arms: they trap
  (`ILLEGAL`); `-DNO_ASSEMBLER` handles both layouts.
- `Palette24Bit` and the
  24-bit loaders `AmigaHardware::setPalette24Bit()` and `CopperList::setPalette24Bit()` (BPLCON3
  banks, high nibbles then LOCT). `setPalette24Bit()` restores bank 0 with LOCT clear afterwards.
- `daj_math.h`: the 16-bit `mulu.w`/`divu.w` helpers the framework uses instead of 32-bit software
  multiply and divide.
- Neutral prefixes: `DAJ_SASC_ALIAS`, `DAJ_BLIT_IRQ`, `daj_mulu16`.

Build flags as in the ports: `m68k-amiga-elf-gcc -m68000 -msoft-float -fno-rtti -fno-exceptions
-std=gnu++17 -fpermissive -include SASCCompat.h -I. -Icompat-include`. The objects need from the
program: `SysBase`, `operator new`/`delete`, `memcpy`/`memset`, and `__mulsi3` only if
`Bitmap::patternWithMask()` is called (it breaks a mul/div link audit).

## Known gaps

- **AGA fetch window**: `setPlayfield()` sets FMODE 3 on AGA with an unmeasured DDF pair. The ports
  that run FMODE 3 write measured values of their own (comment in `AmigaHardware.cpp`).
- **AGA detection** is the caller's: require both the ALICE and LISA flags (some Kickstarts set
  only one), or read the chip ID registers.
- **`BPLCON4`** is not cleared on AGA; an inherited value remaps every pen; clear it in the caller.
- No memory or runtime layer of its own; rectangle chunky-to-planar conversion is in
  [`kalms-c2p`](../kalms-c2p/README.md).
