# AmigaXDev

The shared development environment for the Amiga game projects: game ports, WHDLoad slave
improvements, and branches of JOTD's and StingRay's slave repositories. `make setup` installs
the cross toolchain, emulators, WHDLoad, Kickstarts and everything else the projects take from
`~/.local`, the same on every Mac. The repo also holds the documentation the projects share:
the playbooks in `docs/playbooks/`.

## Setting up a Mac

Prerequisites: an Apple Silicon Mac with the Xcode command line tools (`xcode-select --install`)
and [Homebrew](https://brew.sh), with Homebrew's `bin` ahead of `/bin` on `PATH` (the
`brew shellenv` line the installer suggests does that): the projects' scripts run under
`#!/usr/bin/env bash` and need the bash 5 that setup installs, not macOS's 3.2. Then:

```sh
git clone <this repo> AmigaXDev && cd AmigaXDev
make setup TOSEC=<TOSEC tree> AMIGA_OS=<Workbench directory> DEVCD=<Developer CD>
```

`make setup` installs Rosetta 2 if needed (the gdb-stub FS-UAE and vasm are x86_64), the
Homebrew packages in `Brewfile` and `Brewfile.extras`, then everything below, and ends with
`make check`. A rerun skips what is already installed and current, so it is also how to
update. It takes about half an hour on a fresh machine, mostly the two FS-UAE builds.

### The Kickstart, Workbench and Developer CD sources

Kickstarts, Workbench disks and the Amiga Developer CD are copyrighted, so they are neither in this repo nor
downloaded from a fixed address. You name the source, as a local directory or an `http(s)://`
URL:

- `TOSEC` is the root of a Commodore Amiga TOSEC tree, the directory that holds `Firmware/`.
  Setup takes `Firmware/<TOSEC name>.zip` for each ROM in `manifest/roms.tsv`.
- `AMIGA_OS` is a flat directory of TOSEC-named Workbench zips, laid out like the Internet
  Archive item "Commodore Amiga - Operating Systems - Workbench". Setup takes the zips named
  in `manifest/os.tsv`. SetPatch comes out of the Workbench 3.1 disk with `xdftool`.
- `DEVCD` is the Amiga Developer CD v2.1 ISO, or a directory that holds it under its Internet
  Archive name (`manifest/devcd.tsv`). Setup installs the CD's `Reference/` directory: the ROM
  Kernel Manuals (Hardware, Libraries, Devices) and autodocs, as AmigaGuide and as HTML.

Every file is checked against the sha256 in the manifest before it is installed. The
variables can be left out once those files are installed.

## What gets installed where

| Component | `make` target | Source | Installed as |
|---|---|---|---|
| m68k gcc/gdb/objdump, vasm, elf2hunk, Shrinkler, exe2adf, FS-UAE with the Barto gdb stub (x86_64), gcc8 support files | `toolchain` | BartmanAbyss amiga-debug 1.8.2 (GitHub release `.vsix`) | `~/.local/{opt,fs-uae,support}`, `~/.local/vasmm68k_mot` etc. |
| WHDLoad 20.0 and 19.2 developer packages | `whdload` | whdload.de | `WHDLoad-20.0/`, `WHDLoad/` |
| NDK 3.2 Release 4 | `ndk` | Aminet `dev/misc/NDK3.2` | `ndk/` |
| Installer 43.3 | `installer` | Aminet `util/misc/Installer-43_3` | `Installer43/Installer` |
| Kickstart relocation tables (`.RTB`) | `rtb` | Aminet `util/boot/skick346` | `Kickstarts/*.RTB` |
| Kickstarts 1.2, 1.3, 2.04, 3.1 (A600), 3.1 (A1200) | `roms` | your TOSEC tree | `Kickstarts/` |
| Developer CD 2.1 `Reference/`: Hardware Reference Manual and the other RKMs, autodocs, Amiga Mail | `devcd` | your Developer CD | `adcd21/Reference/` |
| AGA hardware reference (AmigaGuide) | `aga-guide` | Aminet `docs/misc/agamanual` | `AGA.Guide` |
| Workbench 2.04 disk 1, SetPatch 40.16 | `os` | your Workbench directory | `Workbenchv2.04rev37.67Workbench.adf`, `SetPatch` |
| Kalms c2p routines | `kalms` | GitHub `Kalmalyzer/kalms-c2p` | `kalms-c2p/` |
| LHa for UNIX (creates `.lha`) | `lha` | GitHub `jca02266/lha`, built | `lha-compressor/src/lha` |
| Python 3.12 + Pillow, numpy, capstone, amitools | `python` | PyPI via uv | `python/` |
| Shared `env.sh`, `fsuae_common.sh`, playbooks | `share` | this repo | top level |
| Native arm64 FS-UAE with the gdb stub | `fsuae-arm` | GitHub `grahambates/fs-uae`, built | `fs-uae-arm/` |
| The same with the cycle profiler patch | `fsuae-aprof` | that + `patches/fsuae-aprof.patch` | `fs-uae-aprof/` |
| Ghidra, MAME, DOSBox-X, DOSBox Staging, unicorn, volta, ffmpeg, 7-Zip | `brew-extras` | Homebrew | Homebrew; Ghidra linked under `~/.local/share/ghidra/` |

Paths without a directory are under `~/.local/share/amiga`. Every download, git commit and
licensed file is pinned in `manifest/`. `docs/environment.md` lists the shared variables and
how a project uses them.

Setup never deletes an installed file. A file that differs from the manifest is moved to
`~/.local/share/amiga/.replaced/<time>/` before the new one goes in. The shared files from
this repo are copies: if one was edited in place, setup stops; `make pull-shared` copies the
edit back here to commit.

Downloads are cached in `tmp/cache/` and build trees are in `tmp/build/` (`CACHE=` and `BUILD=`
move them; the FS-UAE builds need a path without spaces). `PREFIX=` installs somewhere other
than `~/.local`, for example to try setup without touching a working environment.
