#!/usr/bin/env bash
# Shared FS-UAE / gdb process handling and launch options for the Amiga project scripts.
# Installed by AmigaXDev into ~/.local/share/amiga; source it right after the script's
# `cd "$(dirname "$0")"` line (amiga/env.sh sets $FSUAE_COMMON):
#
#     . "${FSUAE_COMMON:-$HOME/.local/share/amiga/fsuae_common.sh}"
#
# Several Amiga projects are developed side by side, each with its own fs-uae (and gdb)
# running.  The rules here:
#   * only ever kill a process this script's directory started: one recorded in our pidfile,
#     or an fs-uae whose working directory is ours;
#   * every directory gets its own gdb-stub port; a port another project's emulator holds is
#     skipped, never taken over;
#   * debug runs (DEBUG=1, WARP=1 or FSUAE_QUIET=1) are silent and open their window behind
#     the others; plain runs have sound and a normal window.
#
# Process API:
#   fsuae_stop_previous     kill the emulator the previous run of this script left
#   fsuae_claim_port        pick a free $DEBUG_PORT (implies stop_previous); prints it
#   fsuae_track PID         remember an fs-uae we started (for the next run)
#   fsuae_track_self        same, for the `exec fs-uae ...` case (pid = this shell)
#   fsuae_stop              kill the tracked emulator now
#   fsuae_kill_recorded F C kill the pid in pidfile F if it is still a C process
#   fsuae_gdb_script FILE   echo a copy of FILE with the stub port patched in
# Launch API:
#   fsuae_options           fill the FSUAE_ARGS array from the variables below.  fsuae_launch
#                           and fsuae_exec call it only if FSUAE_ARGS is unset: a script that
#                           calls it itself must set every variable first
#   fsuae_launch ARGS...    start "$FSUAE" in the background with $EXTRA_ARGS, ARGS and
#                           FSUAE_ARGS, log to $FSUAE_RUN/fsuae.log, track it, print its pid.
#                           FS-UAE keeps the first value of a repeated option, so EXTRA_ARGS
#                           beats the script's ARGS, which beat fsuae_options
#   fsuae_exec ARGS...      the same in the foreground (exec), for interactive scripts
# Variables (all optional; a script sets its own defaults before calling fsuae_options):
#   FSUAE (fs-uae on PATH), FSUAE_RUN (work dir, .run), DEBUG_PORT (pins the stub port)
#   AMIGA_MODEL, CPU, CHIP_KB, FAST_KB, SLOW_KB, KICKSTART, WARP=1
#   NTSC=1 (NTSC timing: --ntsc_mode=1 and --uae_ntsc=true)
#   DEBUG=1 (gdb stub, waits $DEBUG_WAIT s, default 20), DETERMINISTIC=1, RECORD=FILE
#   JOY0, JOY1 (an FS-UAE device name; "none" also sets the port's mode to nothing, which is
#     what keeps the host mouse out of a capture)
#   SOUND=1|0 (default 1, 0 for debug runs; SILENT=1 means SOUND=0)
#   WINDOW=front|back|none (default front, back for debug runs).  back keeps the window
#     behind the active one (SDL_MAC_BACKGROUND_APP); none runs with no window at all
#   WINDOW_WIDTH, WINDOW_HEIGHT (default 720x568: without a size a launch with no window
#     stalls with "Not a valid drawable size")
#   EXTRA_ARGS (word-split, passed first, so it overrides everything; --warp_mode=1 in it
#     makes a debug run like WARP=1)

FSUAE_RUN="${FSUAE_RUN:-.run}"
FSUAE_PIDFILE="$FSUAE_RUN/fsuae.pid"

# Default gdb-stub port: derived from the script's own directory, so each project
# (and each checkout) gets a different one and two debug sessions can run at the
# same time.  Deterministic: the same directory always starts from the same port, and
# fsuae_claim_port moves on to the next one only if another project holds it.
# Pin it with $DEBUG_PORT when you need a fixed one (VS Code launch configs etc.).
if [ -z "${DEBUG_PORT:-}" ]; then
  DEBUG_PORT=$(( 2345 + $(printf '%s' "$PWD" | cksum | cut -d' ' -f1) % 400 ))
  FSUAE_PORT_PINNED=0
else
  FSUAE_PORT_PINNED="${FSUAE_PORT_PINNED:-1}"
fi
export DEBUG_PORT FSUAE_PORT_PINNED

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

# True if $1 is an fs-uae this directory started: its working directory is ours (every
# launcher starts it from the script's directory).
fsuae_is_ours() {
  fsuae_is_a "$1" fs-uae || return 1
  [ "$(lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')" = "$(pwd -P)" ]
}

# Make sure the gdb stub port is ours to use.  A leftover fs-uae of this directory on it is
# killed; a port held by anything else (another project's emulator included) is skipped,
# unless $DEBUG_PORT was pinned, in which case we stop rather than shoot a stranger.
fsuae_claim_port() {
  fsuae_stop_previous
  local held pid tries=0 foreign
  while :; do
    held=$(lsof -nP -iTCP:"$DEBUG_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
    [ -n "$held" ] || break
    foreign=""
    for pid in $held; do
      if fsuae_is_ours "$pid"; then
        echo "reclaiming port $DEBUG_PORT from this directory's leftover emulator (pid $pid)"
        kill -9 "$pid" 2>/dev/null || true
      else
        foreign="$pid"
      fi
    done
    if [ -z "$foreign" ]; then sleep 2; continue; fi
    if [ "$FSUAE_PORT_PINNED" = 1 ]; then
      echo "port $DEBUG_PORT is held by pid $foreign, which is not this directory's emulator;" >&2
      echo "stop it yourself or pick another port with \$DEBUG_PORT" >&2
      exit 1
    fi
    tries=$((tries + 1))
    [ "$tries" -lt 50 ] || { echo "no free gdb stub port near $DEBUG_PORT" >&2; exit 1; }
    DEBUG_PORT=$((DEBUG_PORT + 1))
  done
  export DEBUG_PORT
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

# --- launching ---------------------------------------------------------------------------

# A debug run: the gdb stub, warp, or a script that says so (diag/capture scripts).
fsuae_quiet() {
  [ "${DEBUG:-0}" = 1 ] || [ "${WARP:-0}" = 1 ] || [ "${FSUAE_QUIET:-0}" = 1 ] ||
    case " ${EXTRA_ARGS:-} " in *" --warp_mode=1 "*) true ;; *) false ;; esac
}

fsuae_options() {
  local sound window quiet=0
  fsuae_quiet && quiet=1
  sound="${SOUND:-}"
  [ -z "$sound" ] && [ "${SILENT:-0}" = 1 ] && sound=0
  [ -z "$sound" ] && { [ "$quiet" = 1 ] && sound=0 || sound=1; }
  window="${WINDOW:-}"
  [ -z "$window" ] && { [ "$quiet" = 1 ] && window=back || window=front; }
  case "$window" in front|back|none) ;; *) echo "WINDOW must be front, back or none" >&2; exit 1 ;; esac
  FSUAE_WINDOW="$window"

  mkdir -p "$FSUAE_RUN"
  FSUAE_ARGS=(--base_dir="$PWD/$FSUAE_RUN/fsuae" --fullscreen=0 --automatic_input_grab=0
              --window_width="${WINDOW_WIDTH:-720}" --window_height="${WINDOW_HEIGHT:-568}"
              --ntsc_mode="${NTSC:-0}" --warp_mode="${WARP:-0}")
  # ntsc_mode alone leaves this FS-UAE in PAL timing; the core option switches it.
  [ "${NTSC:-0}" = 1 ]      && FSUAE_ARGS+=(--uae_ntsc=true)
  [ -n "${AMIGA_MODEL:-}" ] && FSUAE_ARGS+=(--amiga_model="$AMIGA_MODEL")
  [ -n "${CPU:-}" ]         && FSUAE_ARGS+=(--cpu="$CPU")
  [ -n "${CHIP_KB:-}" ]     && FSUAE_ARGS+=(--chip_memory="$CHIP_KB")
  [ -n "${FAST_KB:-}" ]     && FSUAE_ARGS+=(--fast_memory="$FAST_KB")
  [ -n "${SLOW_KB:-}" ]     && FSUAE_ARGS+=(--slow_memory="$SLOW_KB")
  [ -n "${KICKSTART:-}" ]   && FSUAE_ARGS+=(--kickstart_file="$KICKSTART")
  local n dev
  for n in 0 1; do
    eval "dev=\${JOY$n:-}"
    [ -n "$dev" ] || continue
    FSUAE_ARGS+=(--joystick_port_$n="$dev")
    [ "$dev" = none ] && FSUAE_ARGS+=(--joystick_port_${n}_mode=nothing)
  done
  [ "$sound" = 0 ]      && FSUAE_ARGS+=(--audio_driver=dummy)
  [ "$window" = none ]  && FSUAE_ARGS+=(--video_driver=null)
  [ "${DEBUG:-0}" = 1 ] && FSUAE_ARGS+=(--remote_debugger="${DEBUG_WAIT:-20}" --remote_debugger_port="$DEBUG_PORT")
  [ -n "${RECORD:-}" ]  && FSUAE_ARGS+=(--record="$RECORD" --deterministic=1)
  [ "${DETERMINISTIC:-0}" = 1 ] && FSUAE_ARGS+=(--deterministic=1)
  return 0
}

# Exported for one launch: a background app never comes to the front.
fsuae_env() {
  [ "${FSUAE_WINDOW:-front}" = front ] || export SDL_MAC_BACKGROUND_APP=1
}

fsuae_launch() {
  [ -n "${FSUAE_ARGS+set}" ] || fsuae_options
  local log="${FSUAE_LOG:-$FSUAE_RUN/fsuae.log}"
  # The subshell execs, so $! is the emulator itself (what fsuae_stop_previous checks).
  # shellcheck disable=SC2086  # EXTRA_ARGS is word-split on purpose
  ( fsuae_env; exec "${FSUAE:-fs-uae}" ${EXTRA_ARGS:-} "$@" "${FSUAE_ARGS[@]}" ) > "$log" 2>&1 &
  fsuae_track $!
  echo "fs-uae pid $FSUAE_PID (log $log, port $DEBUG_PORT)"
}

fsuae_exec() {
  [ -n "${FSUAE_ARGS+set}" ] || fsuae_options
  fsuae_track_self
  fsuae_env
  # shellcheck disable=SC2086
  exec "${FSUAE:-fs-uae}" ${EXTRA_ARGS:-} "$@" "${FSUAE_ARGS[@]}"
}
