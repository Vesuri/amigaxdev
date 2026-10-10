# Shared helpers for scripts/setup.sh.  Written for macOS's /bin/bash 3.2: a fresh Mac has no
# newer bash until Homebrew is set up, and setup is what sets it up.

: "${PREFIX:=$HOME/.local}"
: "${AMIGA_SHARE:=$PREFIX/share/amiga}"
: "${CACHE:=$REPO/tmp/cache}"
: "${BUILD:=$REPO/tmp/build}"
STAMP_DIR="$AMIGA_SHARE/.setup"
REPLACED="$AMIGA_SHARE/.replaced/$(date +%Y%m%d-%H%M%S)"

log()  { printf '%s\n' "setup: $*"; }
warn() { printf '%s\n' "setup: WARNING: $*" >&2; }
die()  { printf '%s\n' "setup: ERROR: $*" >&2; exit 1; }

sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }

# sha_ok FILE SHA: the file exists and has that sha256.
sha_ok() { [ -f "$1" ] && [ "$(sha256 "$1")" = "$2" ]; }

# Manifest rows without comments or blank lines.
rows() { grep -v -e '^#' -e '^[[:space:]]*$' "$REPO/manifest/$1"; }

urlencode() { python3 -I -c 'import sys, urllib.parse as u; print(u.quote(sys.argv[1]))' "$1"; }

# fetch URL DEST: download with retries.  503s are expected: the TOSEC mirrors throttle.
fetch() {
  mkdir -p "$(dirname "$2")"
  curl -fsSL --retry 8 --retry-delay 15 --connect-timeout 30 -o "$2.part" "$1" \
    || { rm -f "$2.part"; return 1; }
  mv "$2.part" "$2"
}

# fetch_from BASE RELPATH DEST: BASE is a local directory, a file:// URL or an http(s) URL of a
# directory laid out like the source tree; RELPATH is the file inside it.
fetch_from() {
  case "$1" in
    http://*|https://*)
      local enc="" part rest="$2"
      while [ -n "$rest" ]; do
        part="${rest%%/*}"
        enc="$enc${enc:+/}$(urlencode "$part")"
        case "$rest" in */*) rest="${rest#*/}" ;; *) rest="" ;; esac
      done
      fetch "${1%/}/$enc" "$3" ;;
    *)
      local src="${1#file://}/$2"
      [ -f "$src" ] || return 1
      mkdir -p "$(dirname "$3")"
      cp "$src" "$3" ;;
  esac
}

# download FILE: a file from manifest/downloads.tsv, cached and checked.  Echoes its path.
download() {
  local row sha url file="$CACHE/$1"
  row=$(rows downloads.tsv | awk -F'\t' -v f="$1" '$1 == f') || true
  [ -n "$row" ] || die "$1 is not in manifest/downloads.tsv"
  sha=$(printf '%s' "$row" | cut -f2); url=$(printf '%s' "$row" | cut -f3)
  if ! sha_ok "$file" "$sha"; then
    log "downloading $1" >&2
    fetch "$url" "$file" || die "download failed: $url"
    sha_ok "$file" "$sha" || die "checksum mismatch: $file (expected $sha, got $(sha256 "$file"))"
  fi
  echo "$file"
}

# set_aside PATH: move an installed file or directory that is about to be replaced into
# $AMIGA_SHARE/.replaced/<time>/, keeping its path below $PREFIX.  Nothing is deleted.
set_aside() {
  local rel="${1#$PREFIX/}" dst
  dst="$REPLACED/$rel"
  mkdir -p "$(dirname "$dst")"
  mv "$1" "$dst"
  warn "replaced $1 (the old one is in $dst)"
}

# install_file SRC DEST SHA: put SRC at DEST unless DEST already has that sha256.
install_file() {
  if sha_ok "$2" "$3"; then return 0; fi
  [ -e "$2" ] && set_aside "$2"
  mkdir -p "$(dirname "$2")"
  cp "$1" "$2"
  sha_ok "$2" "$3" || die "checksum mismatch after copying to $2"
  log "installed $2"
}

# sync_tree SRC DEST: make every file under SRC present and identical under DEST.  Files that
# differ are set aside first; files only in DEST are reported and left alone.
sync_tree() {
  python3 -I "$REPO/scripts/sync_tree.py" "$1" "$2" "$REPLACED" "$PREFIX"
}

# stamp NAME VALUE / stamped NAME VALUE: remember what a component was installed from, so
# reruns skip work whose inputs did not change.
stamp() { mkdir -p "$STAMP_DIR"; printf '%s\n' "$2" > "$STAMP_DIR/$1"; }
stamped() { [ -f "$STAMP_DIR/$1" ] && [ "$(cat "$STAMP_DIR/$1")" = "$2" ]; }

# git_checkout NAME DIR: clone the manifest/git.tsv entry NAME into DIR at its pinned commit.
git_checkout() {
  local row commit url
  row=$(rows git.tsv | awk -F'\t' -v n="$1" '$1 == n')
  [ -n "$row" ] || die "$1 is not in manifest/git.tsv"
  commit=$(printf '%s' "$row" | cut -f2); url=$(printf '%s' "$row" | cut -f3)
  if [ ! -d "$2/.git" ]; then
    [ -e "$2" ] && set_aside "$2"
    git clone -q --filter=blob:none "$url" "$2"
  fi
  if [ "$(git -C "$2" rev-parse HEAD)" != "$commit" ]; then
    [ -z "$(git -C "$2" status --porcelain --untracked-files=no)" ] \
      || die "$2 has local changes; commit or remove them before setup moves it to $commit"
    git -C "$2" fetch -q origin "$commit" 2>/dev/null || git -C "$2" fetch -q origin
    git -C "$2" checkout -q --detach "$commit"
  fi
}
