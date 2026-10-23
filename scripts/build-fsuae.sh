#!/bin/bash
# Build a native arm64 FS-UAE with the Barto gdb stub into $AMIGA_SHARE/NAME:
#   scripts/build-fsuae.sh NAME [PATCH]
# Source: the grahambates/fs-uae remote_debugger_barto fork (manifest/git.tsv), plus PATCH if
# given (patches/fsuae-aprof.patch adds `monitor aprof start` / `monitor aprof stop FILE`).
# Every build also gets patches/fsuae-mmu-write-cache.patch (the core fix),
# patches/fsuae-cpu-frequency.patch (explicit CPU frequencies without 32-bit overflow) and
# patches/fsuae-harness.patch (`monitor key`, `monitor fields`, `monitor mouse`,
# `monitor input`, `monitor harness`, whole-space profiling).
# patches/fsuae-input-observer.patch adds side-effect-free guest input snapshots.
# patches/fsuae-determinism.patch initialises two upstream reads of uninitialised memory that
# made otherwise identical runs differ (serial break detection, screenshot columns), and runs
# the indirect UAE board's host threads in lockstep with deterministic mode.
# SDL2_ttf and libmpeg2 are linked statically from pinned tarballs; glib, gettext, libpng,
# freetype and SDL2 come from Homebrew (Brewfile), so rebuild after a major upgrade of those.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib.sh"
[ -d /opt/homebrew/bin ] && PATH="/opt/homebrew/bin:$PATH"

name="$1"; patch="${2:-}"
# git -C resolves patch filenames from the source checkout.
[ -z "$patch" ] || patch="$(cd "$(dirname "$patch")" && pwd)/$(basename "$patch")"
dest="$AMIGA_SHARE/$name"
build="$BUILD/$name"
commit=$(rows git.tsv | awk -F'\t' '$1 == "fs-uae-barto" {print $2}')
url=$(rows git.tsv | awk -F'\t' '$1 == "fs-uae-barto" {print $3}')
core_patch="$REPO/patches/fsuae-mmu-write-cache.patch"
core_sha=$(sha256 "$core_patch")
freq_patch="$REPO/patches/fsuae-cpu-frequency.patch"
freq_sha=$(sha256 "$freq_patch")
harness_patch="$REPO/patches/fsuae-harness.patch"
harness_sha=$(sha256 "$harness_patch")
input_patch="$REPO/patches/fsuae-input-observer.patch"
input_sha=$(sha256 "$input_patch")
register_patch="$REPO/patches/fsuae-register-observer.patch"
register_sha=$(sha256 "$register_patch")
determinism_patch="$REPO/patches/fsuae-determinism.patch"
determinism_sha=$(sha256 "$determinism_patch")
patch_sha=""; [ -n "$patch" ] && patch_sha=$(sha256 "$patch")

# Already built from the same commit and patch: nothing to do.
rev="$dest/source-revision.txt"
if [ -x "$dest/fs-uae" ] && [ -f "$rev" ] && grep -q "$commit" "$rev" \
   && grep -q "core-fix $core_sha" "$rev" \
   && grep -q "cpu-frequency $freq_sha" "$rev" \
   && grep -q "harness $harness_sha" "$rev" \
   && grep -q "input-observer $input_sha" "$rev" \
   && grep -q "register-observer $register_sha" "$rev" \
   && grep -q "determinism $determinism_sha" "$rev" \
   && { [ -z "$patch_sha" ] || grep -q "$patch_sha" "$rev"; } \
   && { [ -n "$patch_sha" ] || ! grep -q " + patch " "$rev"; }; then
  exit 0
fi

# Autotools flags break on spaces.
case "$build$dest" in *' '*) die "$name: build and install paths must not contain spaces (set BUILD=...)" ;; esac
log "building $name (takes several minutes; log in $build/*.log)"
jobs="$(sysctl -n hw.ncpu)"
deps="$build/deps"; src="$build/fs-uae"
rm -rf "$deps"; mkdir -p "$deps"

unpack() { # DOWNLOAD -> directory under $build
  local a; a=$(download "$1")
  tar xzf "$a" -C "$build"
  echo "$build/$(basename "$1" .tar.gz)"
}
dir=$(unpack SDL2_ttf-2.0.15.tar.gz)
(cd "$dir" && ./configure --prefix="$deps" --disable-shared --enable-static >"$build/ttf.log" 2>&1 \
  && make -j"$jobs" install >>"$build/ttf.log" 2>&1) || die "$name: SDL2_ttf failed, see $build/ttf.log"
dir=$(unpack libmpeg2-0.5.1.tar.gz)
# Its 2008 config.guess calls arm64 macOS "arm" (32-bit ARM assembly); use automake's.
cp -f "$(automake --print-libdir)"/config.guess "$(automake --print-libdir)"/config.sub "$dir/.auto/"
(cd "$dir" && ./configure --prefix="$deps" --disable-shared --enable-static --disable-sdl --without-x >"$build/mpeg.log" 2>&1 \
  && make -j"$jobs" -C libmpeg2 install >>"$build/mpeg.log" 2>&1 && make -C include install >>"$build/mpeg.log" 2>&1) \
  || die "$name: libmpeg2 failed, see $build/mpeg.log"

[ -d "$src/.git" ] || git clone -q --filter=blob:none "$url" "$src"
git -C "$src" checkout -q --force "$commit"
git -C "$src" clean -qfdx
git -C "$src" apply --check "$core_patch"
git -C "$src" apply "$core_patch"
git -C "$src" apply "$freq_patch"
git -C "$src" apply "$harness_patch"
git -C "$src" apply "$input_patch"
git -C "$src" apply "$register_patch"
git -C "$src" apply "$determinism_patch"
[ -n "$patch" ] && git -C "$src" apply "$patch"
export PKG_CONFIG_PATH="$deps/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
(cd "$src" && ./bootstrap >"$build/fs-uae.log" 2>&1 \
  && ./configure --disable-jit --disable-x86 \
       SDL2_TTF_CFLAGS="-I$deps/include $(pkg-config --cflags SDL2_ttf)" SDL2_TTF_LIBS="$(pkg-config --static --libs SDL2_ttf freetype2)" \
       LIBMPEG2_CFLAGS="$(pkg-config --cflags libmpeg2)" LIBMPEG2_LIBS="$(pkg-config --static --libs libmpeg2 libmpeg2convert)" \
       CFLAGS=-O2 CXXFLAGS=-O2 >>"$build/fs-uae.log" 2>&1 \
  && make -j"$jobs" >>"$build/fs-uae.log" 2>&1) || die "$name: FS-UAE failed, see $build/fs-uae.log"
"$src/fs-uae" --version >/dev/null 2>&1 || die "$name: the new binary does not run"

[ -e "$dest" ] && set_aside "$dest"
mkdir -p "$dest"
cp -f "$src/fs-uae" "$src/fs-uae.dat" "$dest/"
cp -R "$src/data" "$dest/data"
{
  printf '%s %s core-fix %s cpu-frequency %s harness %s' "$url" "$commit" "$core_sha" "$freq_sha" "$harness_sha"
  printf ' register-observer %s' "$register_sha"
  printf ' input-observer %s' "$input_sha"
  printf ' determinism %s' "$determinism_sha"
  [ -n "$patch" ] && printf ' + patch %s %s' "$(basename "$patch")" "$patch_sha"
  printf '\nSDL2_ttf 2.0.15 and libmpeg2 0.5.1 static; arm64; JIT disabled\n'
} > "$rev"
log "installed $dest/fs-uae"
