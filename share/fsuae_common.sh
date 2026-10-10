#!/usr/bin/env bash
# Shared FS-UAE / gdb process handling for the Amiga project run/debug/probe scripts.
# It lives outside all the project repos; source it right after the script's
# `cd "$(dirname "$0")"` line:
#
#     . "${FSUAE_COMMON:-$HOME/.local/share/amiga/fsuae_common.sh}"
#
# Why this exists: several Amiga projects are developed side by side, each with its
# own fs-uae (and gdb) running.  The scripts used to `pkill -9 fs-uae`, which shot
# down the other projects' emulators too.  The rules here:
#   * only ever kill a process this script started (tracked by pid),
#   * only ever reclaim OUR gdb-stub port, and only from an fs-uae,
#   * every project gets its own default stub port, so two debug sessions coexist.
#
# API:
#   fsuae_stop_previous     kill the emulator the previous run of this script left
#   fsuae_claim_port        make sure $DEBUG_PORT is free (implies stop_previous)
#   fsuae_track PID         remember an fs-uae we started (for the next run)
#   fsuae_track_self        same, for the `exec fs-uae ...` case (pid = this shell)
#   fsuae_stop              kill the tracked emulator now
#   fsuae_kill_recorded F C kill the pid in pidfile F if it is still a C process
#   fsuae_gdb_script FILE   echo a copy of FILE with the stub port patched in
# Variables: $DEBUG_PORT (override the stub port), $FSUAE_RUN (work dir, default .run).

FSUAE_RUN="${FSUAE_RUN:-.run}"
FSUAE_PIDFILE="$FSUAE_RUN/fsuae.pid"

# Default gdb-stub port: derived from the script's own directory, so each project
# (and each checkout) gets a different one and two debug sessions can run at the
# same time.  Deterministic — the same directory always yields the same port.
# Pin it with $DEBUG_PORT when you need a fixed one (VS Code launch configs etc.).
if [ -z "${DEBUG_PORT:-}" ]; then
  DEBUG_PORT=$(( 2345 + $(printf '%s' "$PWD" | cksum | cut -d' ' -f1) % 40 ))
fi
export DEBUG_PORT

# True if $1 is a live process whose name contains $2 — every kill is guarded with
# this, because a recorded pid may long since have been recycled by something else.
fsuae_is_a() {
  ps -o comm= -p "$1" 2>/dev/null | grep -q "$2"
}

# Kill the pid recorded in pidfile $1, if it is still a $2 process. Removes the file.
fsuae_kill_recorded() {
  local pidfile="$1" comm="$2" pid
  [ -f "$pidfile" ] || return 1
  pid=$(cat "$pidfile" 2>/dev/null)
  rm -f "$pidfile"
  if [ -n "${pid:-}" ] && fsuae_is_a "$pid" "$comm"; then
    echo "stopping this project's leftover $comm (pid $pid)"
    kill -9 "$pid" 2>/dev/null || true
    return 0
  fi
  return 1
}

# Clean up after the previous run of a script in this directory — and only that.
fsuae_stop_previous() {
  # `if`, not `&&`: under `set -e` a failing && list would take the caller down.
  if fsuae_kill_recorded "$FSUAE_PIDFILE" fs-uae; then sleep 1; fi
  return 0
}

# Make sure the gdb stub port is available.  An fs-uae still listening on it is a
# leftover of ours (other projects default to their own ports), so it is killed;
# anything else is reported and we bail out rather than shoot a stranger.
fsuae_claim_port() {
  fsuae_stop_previous
  local held pid ok=1
  held=$(lsof -nP -iTCP:"$DEBUG_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
  for pid in $held; do
    if fsuae_is_a "$pid" fs-uae; then
      echo "reclaiming port $DEBUG_PORT from a leftover gdb-stub emulator (pid $pid)"
      kill -9 "$pid" 2>/dev/null || true
    else
      echo "port $DEBUG_PORT is held by pid $pid, which is not fs-uae;" >&2
      echo "stop it yourself or pick another port with \$DEBUG_PORT" >&2
      ok=0
    fi
  done
  [ "$ok" = 1 ] || exit 1
  if [ -n "$held" ]; then sleep 2; fi
  echo "gdb stub port: $DEBUG_PORT (override with \$DEBUG_PORT)"
  return 0
}

# Remember an emulator we started, so the next run of this script can clean it up.
fsuae_track() {
  FSUAE_PID="$1"
  mkdir -p "$FSUAE_RUN"
  echo "$FSUAE_PID" > "$FSUAE_PIDFILE"
  return 0
}

# For `exec "$FSUAE" ...`: after the exec this shell's pid IS the emulator's.
fsuae_track_self() { fsuae_track "$$"; }

# Kill the emulator we started (and nobody else's).  Safe to call from a trap.
fsuae_stop() {
  if [ -n "${FSUAE_PID:-}" ] && kill -0 "$FSUAE_PID" 2>/dev/null; then
    kill -9 "$FSUAE_PID" 2>/dev/null || true
  fi
  rm -f "$FSUAE_PIDFILE"
  return 0
}

# The checked-in .gdb scripts hardcode `target remote 127.0.0.1:2345`; run them
# through this to get a copy that connects to $DEBUG_PORT instead.  Echoes the path.
fsuae_gdb_script() {
  local src="$1" dst
  mkdir -p "$FSUAE_RUN"
  dst="$FSUAE_RUN/$(basename "$src")"
  sed "s/127\.0\.0\.1:[0-9][0-9]*/127.0.0.1:$DEBUG_PORT/" "$src" > "$dst"
  echo "$dst"
}
