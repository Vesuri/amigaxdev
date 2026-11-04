# Core host tools for every Amiga project (make brew).

# bash 5: the projects' scripts run under `#!/usr/bin/env bash` and use what macOS's bash 3.2
# lacks (an empty "${array[@]}" under set -u, for one).  AmigaXDev's own scripts stay on
# /bin/bash 3.2, which is what a fresh Mac has.
brew "bash"

# Archives: lhasa's lha extracts .lha, unar/lsar read .lha, .lzx and .zip.  Archives are created
# with LHa for UNIX, which setup builds into $AMIGA_SHARE/lha-compressor.
brew "lhasa"
brew "unar"

# The shared Python environment ($AMIGA_SHARE/python).
brew "uv"

# Native arm64 FS-UAE builds (scripts/build-fsuae.sh) and LHa for UNIX.
brew "autoconf"
brew "automake"
brew "libtool"
brew "pkgconf"
brew "glib"
brew "gettext"
brew "libpng"
brew "freetype"
brew "sdl2-compat"

# Host builds of the ports (SDL2 front ends, asset and audio tools).
brew "sdl2_image"
brew "libsndfile"
brew "coreutils"

# Macintosh HFS volumes (hmount, hcopy, humount) for Mac ports' original data.
brew "hfsutils"

brew "git"
brew "gh"
