#!/bin/bash
# Verify the installed environment: checksums from the manifests, pinned commits, shared files
# equal to this repo's, and every tool actually running.  Exit status 1 if anything fails.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
. "$REPO/scripts/lib.sh"
[ -d /opt/homebrew/bin ] && PATH="/opt/homebrew/bin:$PATH"

fails=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fails=$((fails + 1)); }
check() { # DESCRIPTION COMMAND...
  local d="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi
}

echo "Kickstarts, RTBs and Workbench files ($AMIGA_SHARE)"
while IFS=$'\t' read -r dest sha rest; do
  check "$dest" sha_ok "$AMIGA_SHARE/$dest" "$sha"
  check "$dest.RTB" test -f "$AMIGA_SHARE/$dest.RTB"
done < <(rows roms.tsv)
while IFS=$'\t' read -r dest sha rest; do
  check "$dest" sha_ok "$AMIGA_SHARE/$dest" "$sha"
done < <(rows os.tsv)

echo "Downloaded and built trees"
check "WHDLoad 20.0"           test -x "$AMIGA_SHARE/WHDLoad-20.0/C/WHDLoad" -a -f "$AMIGA_SHARE/WHDLoad-20.0/Src/sources/whdload/kick13.s"
check "WHDLoad 19.2"           test -x "$AMIGA_SHARE/WHDLoad/C/WHDLoad"
check "NDK 3.2"                test -d "$AMIGA_SHARE/ndk/Include_I"
check "Installer 43.3"         test -f "$AMIGA_SHARE/Installer43/Installer"
for n in kalms-c2p:kalms-c2p lha:lha-compressor; do
  want=$(rows git.tsv | awk -F'\t' -v n="${n%%:*}" '$1 == n {print $2}')
  check "${n#*:} at ${want:0:7}" test "$(git -C "$AMIGA_SHARE/${n#*:}" rev-parse HEAD 2>/dev/null)" = "$want"
done
for s in "$REPO"/share/*; do
  check "$(basename "$s") matches this repo" cmp -s "$s" "$AMIGA_SHARE/$(basename "$s")"
done
for s in "$REPO"/docs/playbooks/*.md; do
  check "$(basename "$s") matches this repo" cmp -s "$s" "$AMIGA_SHARE/$(basename "$s")"
done

echo "Tools run"
check "m68k-amiga-elf-gcc"     "$PREFIX/opt/bin/m68k-amiga-elf-gcc" --version
check "m68k-amiga-elf-gdb"     "$PREFIX/opt/bin/m68k-amiga-elf-gdb" --version
check "m68k-amiga-elf-objdump" "$PREFIX/opt/bin/m68k-amiga-elf-objdump" --version
check "elf2hunk"               test -x "$PREFIX/elf2hunk"
check "gcc8 support files"     test -f "$PREFIX/support/gcc8_c_support.c"
# vasm prints its banner and exits non-zero without a source file.
check "vasm (x86_64)"          sh -c "'$PREFIX/vasmm68k_mot' 2>&1 | grep -q 'vasm'"
check "FS-UAE (x86_64)"        "$PREFIX/fs-uae/fs-uae" --version
check "FS-UAE arm64"           "$AMIGA_SHARE/fs-uae-arm/fs-uae" --version
check "FS-UAE aprof"           "$AMIGA_SHARE/fs-uae-aprof/fs-uae" --version
check "LHa for UNIX"           sh -c "'$AMIGA_SHARE/lha-compressor/src/lha' --version 2>&1 | grep -q LHa"
check "Python packages"        "$AMIGA_SHARE/python/bin/python3" -c 'import PIL, numpy, capstone, amitools'
check "xdftool"                "$AMIGA_SHARE/python/bin/xdftool" --help
for t in lha unar lsar uv lldb; do check "$t" command -v "$t"; done
check "shared env.sh sources"  bash -c ". '$AMIGA_SHARE/env.sh' && [ -n \"\$KICKSTART\" ]"

if [ "$fails" = 0 ]; then echo "all checks passed"; else echo "$fails check(s) failed"; exit 1; fi
