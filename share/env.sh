# Shared Amiga development environment, installed by AmigaXDev (`make setup`).
# Source it from a project's amiga/env.sh:
#
#     . "${AMIGA_ENV:-$HOME/.local/share/amiga/env.sh}"
#
# Every variable keeps a value that is already set, so a project (or the caller) overrides a
# default by setting it before sourcing this file.  Missing files are reported, not fatal: not
# every project needs every file.  AmigaXDev docs/environment.md describes each variable.

AMIGA_PREFIX="${AMIGA_PREFIX:-$HOME/.local}"
export AMIGA_SHARE="${AMIGA_SHARE:-$AMIGA_PREFIX/share/amiga}"

# Cross toolchain (amiga-debug): m68k-amiga-elf-gcc/gdb/objdump, vasm, elf2hunk, FS-UAE with the
# Barto gdb stub (x86_64), and the NDK headers that come with the compiler.
export AMIGA_TOOLCHAIN="${AMIGA_TOOLCHAIN:-$AMIGA_PREFIX/opt}"
export VASM="${VASM:-$AMIGA_PREFIX/vasmm68k_mot}"
export NDK="${NDK:-$AMIGA_TOOLCHAIN/m68k-amiga-elf/sys-include}"
# Native arm64 FS-UAE with the gdb stub (lldb cannot attach to it; see the playbook §5).
export FSUAE_ARM="${FSUAE_ARM:-$AMIGA_SHARE/fs-uae-arm/fs-uae}"
# Unicorn 2.1.4 with the arm64 constant-subtract fix (lib/libunicorn.2.dylib, include/), for
# projects that opt in; Homebrew's unicorn dies with SIGILL there (patches/, README.md).
export AMIGA_UNICORN="${AMIGA_UNICORN:-$AMIGA_SHARE/unicorn}"

# Kickstarts: the host ROMs, and the images (with .RTB) that WHDLoad's KickEmu slaves boot.
export KICKSTART="${KICKSTART:-$AMIGA_SHARE/Kickstarts/kick40063.A600}"
export KICKSTART_A1200="${KICKSTART_A1200:-$AMIGA_SHARE/Kickstarts/kick40068.A1200}"
export KICK13="${KICK13:-${KICKSTART13:-$AMIGA_SHARE/Kickstarts/kick34005.A500}}"
export KICKSTART13="${KICKSTART13:-$KICK13}"
export RTB="${RTB:-$KICK13.RTB}"

# Workbench 2.04 boot floppy (C: and Libs:), and SetPatch from Workbench 3.1.
export WORKBENCH_ADF="${WORKBENCH_ADF:-$AMIGA_SHARE/Workbenchv2.04rev37.67Workbench.adf}"
export SETPATCH="${SETPATCH:-$AMIGA_SHARE/SetPatch}"

# WHDLoad 20.0 (Include/, Src/ with the KickEmu sources, C/WHDLoad).  $AMIGA_SHARE/WHDLoad is
# 19.2, for testing older versions.  Commodore's Installer 43.3, for install scripts.
export WHDLOAD="${WHDLOAD:-$AMIGA_SHARE/WHDLoad-20.0}"
export WHDLOAD_BINARY="${WHDLOAD_BINARY:-$WHDLOAD/C/WHDLoad}"
export INSTALLER43="${INSTALLER43:-$AMIGA_SHARE/Installer43/Installer}"

# Reference: the Amiga Developer CD 2.1's Reference/ (ROM_Kernel_Manuals/Hardware_Manual and the
# other RKMs as AmigaGuide, HTML/ the same as web pages, autodocs, Amiga Mail), and the AGA
# register guide.
export ADCD="${ADCD:-$AMIGA_SHARE/adcd21/Reference}"
export AGA_GUIDE="${AGA_GUIDE:-$AMIGA_SHARE/AGA.Guide}"

# Process helper for run scripts (pid-scoped kills, a gdb-stub port per directory), and
# LHa for UNIX, which creates release archives.
export FSUAE_COMMON="${FSUAE_COMMON:-$AMIGA_SHARE/fsuae_common.sh}"
export LHA="${LHA:-$AMIGA_SHARE/lha-compressor/src/lha}"

# PATH: the shared Python environment (Pillow, numpy, capstone, amitools), the cross tools,
# vasm and friends, and the x86_64 FS-UAE.  Each is added once.
for _amiga_dir in "$AMIGA_PREFIX/fs-uae" "$AMIGA_PREFIX" "$AMIGA_TOOLCHAIN/bin" "$AMIGA_SHARE/python/bin"; do
  case ":$PATH:" in *":$_amiga_dir:"*) ;; *) PATH="$_amiga_dir:$PATH" ;; esac
done
export PATH
unset _amiga_dir

for _amiga_file in "$VASM" "$AMIGA_TOOLCHAIN/bin/m68k-amiga-elf-gdb" "$KICKSTART" "$KICK13" \
                   "$WORKBENCH_ADF" "$WHDLOAD_BINARY" "$FSUAE_COMMON"; do
  [ -e "$_amiga_file" ] || echo "amiga env: missing $_amiga_file (run make setup in AmigaXDev)" >&2
done
unset _amiga_file
