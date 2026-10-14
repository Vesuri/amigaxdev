#!/bin/bash
# Install one component of the shared Amiga environment: scripts/setup.sh COMPONENT...
# The Makefile is the front end (make setup, make help); README.md lists the components.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib.sh"

[ -d /opt/homebrew/bin ] && PATH="/opt/homebrew/bin:$PATH"

# --- host prerequisites ----------------------------------------------------------------------

c_host() {
  [ "$(uname -s)" = Darwin ] || die "only macOS is supported"
  xcode-select -p >/dev/null 2>&1 || die "install the Xcode command line tools first: xcode-select --install"
  command -v brew >/dev/null || die "install Homebrew first (https://brew.sh), then rerun"
  # FS-UAE with the gdb stub, vasm and Shrinkler from amiga-debug are x86_64 binaries.
  if [ "$(uname -m)" = arm64 ] && ! arch -x86_64 /usr/bin/true 2>/dev/null; then
    log "installing Rosetta 2 (the amiga-debug FS-UAE and vasm are x86_64)"
    softwareupdate --install-rosetta --agree-to-license
  fi
}

# brew_bundle FILE: install what FILE lists and is missing; never upgrade what is there.
brew_bundle() {
  brew bundle check --quiet --no-upgrade --file="$1" >/dev/null 2>&1 && return 0
  log "Homebrew packages ($(basename "$1"))"
  brew bundle --quiet --no-upgrade --file="$1"
}

c_brew() { brew_bundle "$REPO/Brewfile"; }

c_brew_extras() {
  brew_bundle "$REPO/Brewfile.extras"
  # Projects reach Ghidra through ~/.local/share/ghidra/ghidra_<major.minor>_PUBLIC.
  local v link target
  v=$(brew list --versions ghidra | awk '{print $2}' | cut -d. -f1-2)
  [ -n "$v" ] || die "ghidra is not installed"
  link="$PREFIX/share/ghidra/ghidra_${v}_PUBLIC"; target="$(brew --prefix)/opt/ghidra/libexec"
  [ "$(readlink "$link" 2>/dev/null)" = "$target" ] && return 0
  mkdir -p "$PREFIX/share/ghidra"
  ln -sfn "$target" "$link"
  log "linked $link"
}

c_python() {
  local req="$REPO/manifest/python.txt" key
  key=$(sha256 "$req")
  if stamped python "$key" && [ -x "$AMIGA_SHARE/python/bin/python3" ]; then return 0; fi
  log "Python environment $AMIGA_SHARE/python"
  command -v uv >/dev/null || die "uv is missing (it comes from the Brewfile)"
  [ -e "$AMIGA_SHARE/python" ] && set_aside "$AMIGA_SHARE/python"
  UV_CACHE_DIR="$CACHE/uv" uv venv -q --managed-python --python 3.12 "$AMIGA_SHARE/python"
  UV_CACHE_DIR="$CACHE/uv" uv pip install -q --python "$AMIGA_SHARE/python/bin/python3" -r "$req"
  stamp python "$key"
}

# --- downloaded, unchanged inputs ------------------------------------------------------------

c_toolchain() {
  # BartmanAbyss amiga-debug: its bin/darwin tree is ~/.local (gcc, gdb, FS-UAE with the gdb
  # stub, vasm, elf2hunk, Shrinkler, exe2adf) and template/support holds gcc8_*_support.
  local vsix st="$BUILD/amiga-debug" f
  installed toolchain "$(manifest_sha amiga-debug-1.8.2.vsix)" "$PREFIX/opt/bin/m68k-amiga-elf-gcc" \
    "$PREFIX/fs-uae/fs-uae" "$PREFIX/vasmm68k_mot" "$PREFIX/support" && return 0
  vsix=$(download amiga-debug-1.8.2.vsix)
  log "amiga-debug toolchain into $PREFIX"
  rm -rf "$st"; mkdir -p "$st"
  unzip -q "$vsix" 'extension/bin/darwin/*' 'extension/template/support/*' -d "$st"
  # The .vsix stores no Unix modes (the editor extension sets them when it starts): make the
  # Mach-O binaries and scripts executable and everything else plain.
  python3 -I - "$st" <<'EOF'
import os, sys
EXEC = (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa\xcf')
for root, dirs, files in os.walk(sys.argv[1]):
    for f in files:
        p = os.path.join(root, f)
        with open(p, 'rb') as h:
            head = h.read(4)
        os.chmod(p, 0o755 if head in EXEC or head[:2] == b'#!' else 0o644)
EOF
  for f in "$st"/extension/bin/darwin/*; do
    if [ -d "$f" ]; then sync_tree "$f" "$PREFIX/$(basename "$f")"
    else install_file "$f" "$PREFIX/$(basename "$f")" "$(sha256 "$f")"; fi
  done
  sync_tree "$st/extension/template/support" "$PREFIX/support"
  rm -rf "$st"
  stamp toolchain "$(sha256 "$vsix")"
}

c_whdload() {
  local archive=WHDLoad_20.1_dev.lzx dest="$AMIGA_SHARE/WHDLoad"
  local a file sha current=1 st="$BUILD/whdload" legacy="$AMIGA_SHARE/WHDLoad-20.0"
  stamped WHDLoad "$(manifest_sha "$archive")" || current=0
  [ ! -L "$dest" ] || current=0
  while IFS=$'\t' read -r file sha; do
    sha_ok "$dest/$file" "$sha" || current=0
  done < <(rows whdload.tsv)
  if [ "$current" = 0 ]; then
    a=$(download "$archive")
    rm -rf "$st"; mkdir -p "$st"
    unar -q -D -o "$st" "$a" >/dev/null
    while IFS=$'\t' read -r file sha; do
      sha_ok "$st/WHDLoad/$file" "$sha" || die "WHDLoad package mismatch: $file"
    done < <(rows whdload.tsv)
    mkdir -p "$st/WHDLoad/Src/qa/data/dir" "$AMIGA_SHARE"
    # Replace the whole tree, preserving the old one without retaining obsolete files.
    if [ -e "$dest" ] || [ -L "$dest" ]; then set_aside "$dest"; fi
    mv "$st/WHDLoad" "$dest"
    stamp WHDLoad "$(sha256 "$a")"
  fi
  # Retire old developer paths without compatibility aliases.
  if [ -e "$legacy" ] || [ -L "$legacy" ]; then set_aside "$legacy"; fi
  [ ! -e "$AMIGA_SHARE/WHDLoad_dev-20.0.lha" ] || set_aside "$AMIGA_SHARE/WHDLoad_dev-20.0.lha"
  [ ! -e "$STAMP_DIR/WHDLoad-20.0" ] || set_aside "$STAMP_DIR/WHDLoad-20.0"
}

c_ndk() {
  local a st="$BUILD/ndk"
  installed ndk "$(manifest_sha NDK3.2.lha)" "$AMIGA_SHARE/ndk/Include_I" && return 0
  a=$(download NDK3.2.lha)
  rm -rf "$st"; mkdir -p "$st"
  unar -q -D -o "$st" "$a" >/dev/null
  sync_tree "$st" "$AMIGA_SHARE/ndk"
  rm -rf "$st"
  stamp ndk "$(sha256 "$a")"
}

c_installer() {
  local a st="$BUILD/installer"
  installed installer "$(manifest_sha Installer-43_3.lha)" "$AMIGA_SHARE/Installer43/Installer" && return 0
  a=$(download Installer-43_3.lha)
  rm -rf "$st"; mkdir -p "$st"
  unar -q -D -o "$st" "$a" >/dev/null
  install_file "$st/Installer43_3/Installer" "$AMIGA_SHARE/Installer43/Installer" \
    "$(sha256 "$st/Installer43_3/Installer")"
  rm -rf "$st"
  stamp installer "$(sha256 "$a")"
}

c_rtb() {
  # WHDLoad's Kickstart relocation tables, one per ROM in manifest/roms.tsv.
  local a st="$BUILD/skick" dest rtb key
  key="$(manifest_sha skick346.lha)$(sha256 "$REPO/manifest/roms.tsv")"
  # shellcheck disable=SC2046  # one path per ROM, none with spaces
  installed rtb "$key" $(rows roms.tsv | cut -f1 | sed "s|.*|$AMIGA_SHARE/&.RTB|") && return 0
  a=$(download skick346.lha)
  rm -rf "$st"; mkdir -p "$st"
  unar -q -D -o "$st" "$a" >/dev/null
  rows roms.tsv | while IFS=$'\t' read -r dest sha rel; do
    rtb="$st/Kickstarts/$(basename "$dest").RTB"
    [ -f "$rtb" ] || die "skick346 has no $(basename "$rtb")"
    install_file "$rtb" "$AMIGA_SHARE/$dest.RTB" "$(sha256 "$rtb")"
  done
  rm -rf "$st"
  stamp rtb "$key"
}

# --- git checkouts and builds ----------------------------------------------------------------

c_kalms() {
  git_checkout kalms-c2p "$AMIGA_SHARE/kalms-c2p"
}

c_lha() {
  # LHa for UNIX: the only tool here that creates .lha archives (lhasa only extracts).
  local d="$AMIGA_SHARE/lha-compressor"
  git_checkout lha "$d"
  if [ -x "$d/src/lha" ] && stamped lha "$(git -C "$d" rev-parse HEAD)"; then return 0; fi
  if [ -x "$d/src/lha" ] && [ ! -f "$STAMP_DIR/lha" ] && "$d/src/lha" --version >/dev/null 2>&1; then
    stamp lha "$(git -C "$d" rev-parse HEAD)"   # built before setup existed
    return 0
  fi
  log "building LHa for UNIX"
  (cd "$d" && autoreconf -is >/dev/null 2>&1 && ./configure -q && make -s >/dev/null) \
    || die "LHa build failed in $d"
  stamp lha "$(git -C "$d" rev-parse HEAD)"
}

c_fsuae_arm()   { "$REPO/scripts/build-fsuae.sh" fs-uae-arm; }
c_fsuae_aprof() { "$REPO/scripts/build-fsuae.sh" fs-uae-aprof "$REPO/patches/fsuae-aprof.patch"; }

c_unicorn() {
  # Unicorn 2.1.4 with patches/unicorn-aarch64-addsub2.patch: Homebrew's 2.1.4 dies with SIGILL
  # on arm64 where a subtract with borrow folds to a constant.  Homebrew's stays installed.
  local a key st="$BUILD/unicorn" dest="$AMIGA_SHARE/unicorn"
  local patch="$REPO/patches/unicorn-aarch64-addsub2.patch"
  key="$(manifest_sha unicorn-2.1.4.tar.gz)$(sha256 "$patch")"
  installed unicorn "$key" "$dest/lib/libunicorn.2.dylib" "$dest/include/unicorn/unicorn.h" && return 0
  command -v cmake >/dev/null || die "cmake is missing (it comes from Brewfile.extras)"
  a=$(download unicorn-2.1.4.tar.gz)
  log "building Unicorn 2.1.4 (a few minutes; log in $st/build.log)"
  rm -rf "$st"; mkdir -p "$st"
  tar xzf "$a" -C "$st"
  patch -p1 -s -N -d "$st/unicorn-2.1.4" < "$patch" || die "unicorn: $patch does not apply"
  cmake -S "$st/unicorn-2.1.4" -B "$st/build" -DCMAKE_BUILD_TYPE=Release -DUNICORN_BUILD_TESTS=OFF \
    -DCMAKE_INSTALL_PREFIX="$dest" -DCMAKE_INSTALL_NAME_DIR="$dest/lib" >"$st/build.log" 2>&1 \
    && cmake --build "$st/build" -j"$(sysctl -n hw.ncpu)" >>"$st/build.log" 2>&1 \
    || die "unicorn: build failed, see $st/build.log"
  "$AMIGA_SHARE/python/bin/python3" -I "$REPO/scripts/test_unicorn.py" "$st/build/libunicorn.2.dylib" \
    || die "unicorn: the new library fails scripts/test_unicorn.py"
  [ -e "$dest" ] && set_aside "$dest"
  cmake --install "$st/build" >>"$st/build.log" 2>&1 || die "unicorn: install failed, see $st/build.log"
  rm -rf "$st"
  stamp unicorn "$key"
  log "installed $dest"
}

# --- licensed inputs -------------------------------------------------------------------------

need_source() { # VAR WHAT
  eval "local v=\${$1:-}"
  [ -n "$v" ] || die "$2 are missing or wrong; rerun with $1=<path or URL> (see README.md)"
}

c_roms() {
  local dest sha rel out st="$BUILD/roms" rom
  rows roms.tsv | while IFS=$'\t' read -r dest sha rel; do
    out="$AMIGA_SHARE/$dest"
    sha_ok "$out" "$sha" && continue
    need_source TOSEC "Kickstart ROMs"
    log "fetching $(basename "$rel")"
    rm -rf "$st"; mkdir -p "$st"
    fetch_from "$TOSEC" "$rel" "$st/rom.zip" || die "could not fetch $rel from $TOSEC"
    (cd "$st" && unzip -q rom.zip)
    rom=$(find "$st" -name '*.rom' | head -1)
    [ -n "$rom" ] || die "$rel holds no .rom"
    sha_ok "$rom" "$sha" || die "$rel: checksum mismatch (expected $sha)"
    install_file "$rom" "$out" "$sha"
    rm -rf "$st"
    sleep 3   # the TOSEC mirrors throttle bursts
  done
  # run.sh copies the Kickstarts onto a writable Amiga drive; see the playbook §4.
  chmod u+w "$AMIGA_SHARE"/Kickstarts/* 2>/dev/null || true
}

c_os() {
  local dest sha zip member out st="$BUILD/os" adf
  rows os.tsv | while IFS=$'\t' read -r dest sha zip member; do
    out="$AMIGA_SHARE/$dest"
    sha_ok "$out" "$sha" && continue
    need_source AMIGA_OS "Workbench files"
    log "fetching $zip"
    rm -rf "$st"; mkdir -p "$st"
    fetch_from "$AMIGA_OS" "$zip" "$st/disk.zip" || die "could not fetch $zip from $AMIGA_OS"
    (cd "$st" && unzip -q disk.zip)
    adf=$(find "$st" -name '*.adf' | head -1)
    [ -n "$adf" ] || die "$zip holds no .adf"
    if [ -n "$member" ]; then
      [ -x "$AMIGA_SHARE/python/bin/xdftool" ] || die "xdftool is missing; run make python first"
      "$AMIGA_SHARE/python/bin/xdftool" "$adf" read "$member" "$st/member" >/dev/null
      install_file "$st/member" "$out" "$sha"
    else
      install_file "$adf" "$out" "$sha"
    fi
    rm -rf "$st"
  done
}

c_devcd() {
  # The Amiga Developer CD's reference manuals: the RKMs (Libraries, Devices, Hardware) and
  # autodocs as AmigaGuide and HTML, Amiga Mail and the DevCon notes.
  local name sha dirs iso="$CACHE/adcd21.iso" st="$BUILD/devcd"
  IFS=$'\t' read -r name sha dirs < <(rows devcd.tsv)
  installed devcd "$sha" "$AMIGA_SHARE/adcd21/Reference/ROM_Kernel_Manuals/Hardware_Manual" && return 0
  if ! sha_ok "$iso" "$sha"; then
    need_source DEVCD "The Amiga Developer CD"
    log "fetching $name"
    case "$DEVCD" in
      # A URL of the ISO itself is used as given (it is usually already %-encoded).
      http://*.iso|https://*.iso|http://*.ISO|https://*.ISO) fetch "${DEVCD// /%20}" "$iso" ;;
      *.iso|*.ISO) fetch_from "$(dirname "$(local_path "$DEVCD")")" "$(basename "$DEVCD")" "$iso" ;;
      *)           fetch_from "$DEVCD" "$name" "$iso" ;;
    esac || die "could not fetch the Developer CD from $DEVCD (a path or URL of the ISO, or of the directory holding \"$name\")"
    sha_ok "$iso" "$sha" || die "$name: checksum mismatch (expected $sha)"
  fi
  rm -rf "$st"; mkdir -p "$st"
  # shellcheck disable=SC2086  # dirs is a space-separated list
  bsdtar -xf "$iso" -C "$st" $dirs
  chmod -R u+rwX "$st"   # the ISO gives some directories no x bit
  sync_tree "$st" "$AMIGA_SHARE/adcd21"
  rm -rf "$st"
  stamp devcd "$sha"
}

c_aga_guide() {
  # The AGA chipset registers, which the Hardware Reference Manual (OCS/ECS) predates.
  local a st="$BUILD/agaguide"
  installed aga-guide "$(manifest_sha agamanual.lha)" "$AMIGA_SHARE/AGA.Guide" && return 0
  a=$(download agamanual.lha)
  rm -rf "$st"; mkdir -p "$st"
  unar -q -D -o "$st" "$a" >/dev/null
  install_file "$st/AGA.Guide" "$AMIGA_SHARE/AGA.Guide" "$(sha256 "$st/AGA.Guide")"
  rm -rf "$st"
  stamp aga-guide "$(sha256 "$a")"
}

# --- files tracked in this repo --------------------------------------------------------------

# Hand-written shared files: installed as copies, but never over an edit made in place.
# Everything under share/ keeps its path below $AMIGA_SHARE (share/pylib/amigaxdev/env.py ->
# pylib/amigaxdev/env.py); the playbooks go to the top level.
tracked_files() {
  (cd "$REPO" && find share -type f ! -name '*.pyc' ! -path '*/__pycache__/*' ! -name .DS_Store) |
    LC_ALL=C sort | while read -r f; do echo "$f ${f#share/}"; done
  for f in "$REPO"/docs/playbooks/*.md; do echo "docs/playbooks/${f##*/} ${f##*/}"; done
}

# The shared venv finds the amigaxdev package through a .pth file in its site-packages.
pylib_pth() {
  local site
  [ -x "$AMIGA_SHARE/python/bin/python3" ] || return 0
  site=$("$AMIGA_SHARE/python/bin/python3" -I -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  if [ "$(cat "$site/amigaxdev.pth" 2>/dev/null)" != "$AMIGA_SHARE/pylib" ]; then
    echo "$AMIGA_SHARE/pylib" > "$site/amigaxdev.pth"
    log "installed $site/amigaxdev.pth"
  fi
}

c_share() {
  local src dst
  tracked_files | while read -r src dst; do
    dst="$AMIGA_SHARE/$dst"
    if [ -f "$dst" ] && ! cmp -s "$REPO/$src" "$dst"; then
      if [ -f "$STAMP_DIR/share/$src" ] && cmp -s "$STAMP_DIR/share/$src" "$dst"; then
        :   # unchanged since the last install: the repo copy is newer
      else
        die "$dst was edited in place; run make pull-shared, commit, then rerun"
      fi
    fi
    mkdir -p "$(dirname "$dst")" "$(dirname "$STAMP_DIR/share/$src")"
    cmp -s "$REPO/$src" "$dst" 2>/dev/null || { cp "$REPO/$src" "$dst"; log "installed $dst"; }
    cp "$REPO/$src" "$STAMP_DIR/share/$src"
  done
  pylib_pth
}

c_pull_shared() {
  # Copy shared files that were edited in place back into the repo, for review and commit.
  local src dst
  tracked_files | while read -r src dst; do
    dst="$AMIGA_SHARE/$dst"
    if [ -f "$dst" ] && ! cmp -s "$REPO/$src" "$dst"; then
      cp "$dst" "$REPO/$src"
      mkdir -p "$(dirname "$STAMP_DIR/share/$src")"; cp "$dst" "$STAMP_DIR/share/$src"
      log "pulled $dst into $src"
    fi
  done
}

for c in "$@"; do
  fn="c_$(printf '%s' "$c" | tr '-' '_')"
  declare -F "$fn" >/dev/null || die "unknown component: $c"
  "$fn"
done
