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
#   fsuae_claim_port        pick a free $DEBUG_PORT (implies stop_previous); prints it.  With
#                           FSUAE_CLAIM_STRICT=1 it never takes or moves a port: any listener
#                           on $DEBUG_PORT, even this directory's, makes it fail (return 1)
#   fsuae_prepare           before a launch: claim the port for DEBUG=1, else stop_previous
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
#                           The launcher removes lower-priority duplicates, so EXTRA_ARGS
#                           beats AMIGA_SETUP, then the script's ARGS, then fsuae_options
#   fsuae_exec ARGS...      the same in the foreground (exec), for interactive scripts
# Variables (all optional; a script sets its own defaults before calling fsuae_options):
#   FSUAE (fs-uae on PATH), FSUAE_RUN (work dir, .run), DEBUG_PORT (pins the stub port)
#   AMIGA_MODEL, CPU, CHIP_KB, FAST_KB, SLOW_KB, KICKSTART, WARP=1
#   AMIGA_SETUP (named machine; overrides individual machine variables and script arguments)
#   AMIGA_MONITOR=left|right|primary (macOS; unset: debug runs left on multiple displays;
#     ordinary runs unchanged; empty: off)
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
#   FSUAE_TITLE (the window title; {machine} becomes the machine; default: project ·
#     {machine} · gdb port)

FSUAE_RUN="${FSUAE_RUN:-.run}"
FSUAE_PIDFILE="$FSUAE_RUN/fsuae.pid"
_FSUAE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  if [ "${FSUAE_CLAIM_STRICT:-0}" = 1 ]; then
    # Only the recorded process can be reclaimed: an occupied port alone does not establish
    # ownership, even when its listener is an fs-uae started from this directory.
    held=$(lsof -nP -iTCP:"$DEBUG_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$held" ]; then
      echo "debug port $DEBUG_PORT is busy (pid $held); no process stopped" >&2
      return 1
    fi
    echo "gdb stub port: $DEBUG_PORT (override with \$DEBUG_PORT)"
    return 0
  fi
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

# What a run script does before launching: a debug run needs the stub port, any run replaces
# the previous run of this directory.
fsuae_prepare() {
  if [ "${DEBUG:-0}" = 1 ]; then fsuae_claim_port; else fsuae_stop_previous; fi
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

# Applied late so project defaults cannot replace an explicitly selected machine. Keep a
# separate argument array ahead of project arguments (FS-UAE keeps the first occurrence).
# Kickstart 3.1 is intentional even on A500: these projects boot directory hard drives.
fsuae_setup() {
  FSUAE_SETUP_ARGS=()
  [ -n "${AMIGA_SETUP:-}" ] || return 0
  local chipset mmu=0 fpu=0 frequency exact=true data_cache=false
  local share="${AMIGA_SHARE:-${AMIGA_PREFIX:-$HOME/.local}/share/amiga}"
  case "$AMIGA_SETUP" in
    a500|a500-1.5m|a500+)
      AMIGA_MODEL=A500 CPU=68000 CHIP_KB=512 FAST_KB=0 SLOW_KB=512
      [ "$AMIGA_SETUP" = a500-1.5m ] && SLOW_KB=1536
      chipset=ocs frequency=7093790
      [ "${NTSC:-0}" = 1 ] && frequency=7159090
      if [ "$AMIGA_SETUP" = a500+ ]; then
        AMIGA_MODEL=A500+ CHIP_KB=1024 SLOW_KB=0 chipset=ecs
      fi
      KICKSTART="$share/Kickstarts/kick40063.A600"
      ;;
    a3000)
      AMIGA_MODEL=A3000 CPU=68030 CHIP_KB=2048 FAST_KB=8192 SLOW_KB=0
      chipset=ecs mmu=68030 fpu=68882 frequency=25000000 data_cache=true
      # Shared ECS 3.1 ROM supports directory drives; native A3000 SCSI needs its own ROM.
      KICKSTART="${KICKSTART_A3000:-$share/Kickstarts/kick40063.A600}"
      ;;
    a1200|a1200-fast|a1200-030|a1200-040|a1200-060)
      AMIGA_MODEL=A1200 CPU=68EC020 CHIP_KB=2048 FAST_KB=8192 SLOW_KB=0
      chipset=aga frequency=14187580
      [ "${NTSC:-0}" = 1 ] && frequency=14318180
      KICKSTART="${KICKSTART_A1200:-$share/Kickstarts/kick40068.A1200}"
      case "$AMIGA_SETUP" in
        a1200) FAST_KB=0 ;;
        a1200-030) CPU=68030 mmu=68030 frequency=50000000 data_cache=true ;;
        a1200-040) CPU=68040 mmu=68040 fpu=68040 frequency=25000000 exact=false data_cache=true ;;
        a1200-060) CPU=68060 mmu=68060 fpu=68060 frequency=50000000 exact=false data_cache=true ;;
      esac
      ;;
    *)
      echo "Unknown AMIGA_SETUP '$AMIGA_SETUP'; use a500, a500-1.5m, a500+, a3000, a1200, a1200-fast, a1200-030, a1200-040 or a1200-060" >&2
      return 1 ;;
  esac
  export AMIGA_MODEL CPU CHIP_KB FAST_KB SLOW_KB KICKSTART
  FSUAE_SETUP_ARGS=(
    --amiga_model="$AMIGA_MODEL" --uae_mmu_model="$mmu" --uae_fpu_model="$fpu"
    --cpu="$CPU" --kickstart_file="$KICKSTART"
    --chip_memory="$CHIP_KB" --fast_memory="$FAST_KB" --slow_memory="$SLOW_KB"
    --zorro_iii_memory=0 --uae_mbresmem_size=0 --uae_a3000mem_size=0
    --uae_chipset="$chipset"
    --jit_compiler=0 --uae_cachesize=0 --uae_cpu_speed=real
    --uae_cpu_multiplier=0 --uae_cpu_frequency="$frequency"
    --uae_cpu_data_cache="$data_cache"
    --uae_cpu_compatible=true --uae_cpu_cycle_exact="$exact"
    --uae_cpu_memory_cycle_exact="$exact" --uae_blitter_cycle_exact="$exact"
  )
  # 020 has only an instruction cache, supplied by the compatible CPU core.
  # 030+ data caches require indirect UAE Boot ROM access for directory drives.
  if [ "$data_cache" = true ]; then
    FSUAE_SETUP_ARGS+=(--uae_uaeboard=full+indirect)
  fi
}

fsuae_options() {
  fsuae_setup || return 1
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

fsuae_monitor_coordinates() {
  python3 "$_FSUAE_COMMON_DIR/pylib/amigaxdev/monitor.py" "${AMIGA_MONITOR-auto}"
}

# Resolve displays immediately before launch, so reconnecting/rearranging them needs no
# configuration update. Explicit EXTRA_ARGS positions retain priority. No GUI access for
# headless runs, including those requested directly through video_driver.
fsuae_monitor() {
  FSUAE_MONITOR_ARGS=()
  # Use the same debug/diagnostic classification as sound and background windows.
  # Explicit monitor choices still apply to interactive runs.
  if [ -z "${AMIGA_MONITOR+set}" ]; then
    fsuae_quiet || return 0
  fi
  [ "${AMIGA_MONITOR-unset}" != "" ] || return 0
  case "${AMIGA_MONITOR-auto}" in
    auto|left|right|primary) ;;
    *) echo "Unknown AMIGA_MONITOR '$AMIGA_MONITOR'; use left, right or primary" >&2; return 1 ;;
  esac
  local arg coordinates x y
  for arg in "$@"; do
    case "$arg" in
      --video_driver=null) return 0 ;;
      --video_driver=*) break ;;
    esac
  done
  if ! coordinates=$(fsuae_monitor_coordinates); then
    # An unavailable desktop must not prevent an otherwise ordinary default launch.
    [ "${AMIGA_MONITOR-auto}" = auto ] && return 0
    return 1
  fi
  [ -n "$coordinates" ] || return 0
  read -r x y <<< "$coordinates"
  FSUAE_MONITOR_ARGS=(--window_x="$x" --window_y="$y")
}

# Exported for one launch: a background app never comes to the front.
fsuae_env() {
  [ "${FSUAE_WINDOW:-front}" = front ] || export SDL_MAC_BACKGROUND_APP=1
  if [ -n "${FSUAE_MONITOR_ARGS+set}" ] && [ "${#FSUAE_MONITOR_ARGS[@]}" -gt 0 ]; then
    # The bundled x86_64 fsemu ignores CLI window coordinates, and resets even
    # environment coordinates to centred unless window_w/h are supplied too.
    # Read the final argv in first-value-wins order, preserving EXTRA_ARGS overrides.
    local arg x= y= w= h=
    for arg in "$@"; do
      case "$arg" in
        --window_x=*) [ -n "$x" ] || x="${arg#*=}" ;;
        --window_y=*) [ -n "$y" ] || y="${arg#*=}" ;;
        --window_width=*|--window_w=*) [ -n "$w" ] || w="${arg#*=}" ;;
        --window_height=*|--window_h=*) [ -n "$h" ] || h="${arg#*=}" ;;
      esac
    done
    export FSEMU_WINDOW_X="$x" FSEMU_WINDOW_Y="$y"
    export FSEMU_WINDOW_W="${w:-720}" FSEMU_WINDOW_H="${h:-568}"
    export FSEMU_WINDOW_CENTER_X=0 FSEMU_WINDOW_CENTER_Y=0
  fi
  return 0
}

# The window title, so a window shows whose it is and what it runs: $FSUAE_TITLE, else the
# project, the machine and the gdb port of a DEBUG=1 run. The project is the outermost
# checkout's directory name (a clone or worktree in another checkout's tmp/ counts as that
# checkout), but never a repository at or above $HOME. Native builds show the title and
# replace {machine} with the machine as FS-UAE runs it ("68030 MMU AGA 2MB CHIP 8MB FAST");
# the bundled x86_64 one shows "FS-UAE".
fsuae_title() {
  if [ -n "${FSUAE_TITLE:-}" ]; then
    printf '%s' "$FSUAE_TITLE"
    return 0
  fi
  local home root dir main title
  home=$(cd "$HOME" 2>/dev/null && pwd -P)
  root=$(pwd -P) dir=$root
  while main=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null) && [ -n "$main" ]; do
    case "$home/" in "$main"/*) break ;; esac
    root=$main dir=$(dirname "$main")
  done
  title="$(basename "$root") · {machine}"
  [ "${DEBUG:-0}" = 1 ] && title="$title · gdb $DEBUG_PORT"
  printf '%s' "$title"
}

# Separates the argument groups passed to fsuae_resolve_options; never reaches FS-UAE.
FSUAE_GROUP_END=--amigaxdev-group-end

# Resolve duplicates ourselves: raw UAE options are applied again by FS-UAE after
# its ordinary parser, so relying on that parser's first-value-wins is unsafe.
# Arguments arrive in precedence order (explicit overrides, preset, caller, defaults),
# each group ended by $FSUAE_GROUP_END. Fails on a CPU spelling FS-UAE does not know: it
# would warn and run the model's default CPU instead.
fsuae_resolve_options() {
  FSUAE_EFFECTIVE_ARGS=()
  local arg key group seen='|' mmu= fpu= cpu
  for arg in "$@" "$FSUAE_GROUP_END"; do
    if [ "$arg" = "$FSUAE_GROUP_END" ]; then
      # A CPU spelling's MMU/FPU, unless its own group or a higher one set them explicitly
      # (in any order): --cpu=68030 --uae_mmu_model=0 is a 68030 without MMU.
      case "$seen" in *'|--uae_mmu_model|'*) ;;
        *) if [ -n "$mmu" ]; then
             seen="$seen--uae_mmu_model|"; FSUAE_EFFECTIVE_ARGS+=(--uae_mmu_model="$mmu")
           fi ;;
      esac
      case "$seen" in *'|fpu|'*) ;;
        *) if [ -n "$fpu" ]; then
             seen="${seen}fpu|"; FSUAE_EFFECTIVE_ARGS+=(--uae_fpu_model="$fpu")
           fi ;;
      esac
      mmu= fpu=
      continue
    fi
    case "$arg" in
      --*=*) key="${arg%%=*}" ;;
      *) FSUAE_EFFECTIVE_ARGS+=("$arg"); continue ;;
    esac
    group="$key"
    case "$key" in
      --chip_memory|--uae_chipmem_size) group=chip ;;
      --fast_memory|--uae_fastmem_size) group=fast ;;
      --slow_memory|--uae_bogomem_size) group=slow ;;
      --zorro_iii_memory|--uae_z3mem_size) group=z3 ;;
      --motherboard_ram|--uae_a3000mem_size) group=motherboard ;;
      --fpu|--uae_fpu_model) group=fpu ;;
      --cpu|--uae_cpu_model) group=cpu ;;
      --ntsc_mode|--uae_ntsc) group=ntsc ;;
    esac
    case "$seen" in *"|$group|"*) continue ;; esac
    seen="$seen$group|"
    FSUAE_EFFECTIVE_ARGS+=("$arg")
    # CPU spellings imply MMU/FPU selections (added at the end of the group). Preserve
    # explicit settings, but do not let lower-priority raw options undo a CPU override.
    case "$arg" in
      --ntsc_mode=1) FSUAE_EFFECTIVE_ARGS+=(--uae_ntsc=true) ;;
      --ntsc_mode=0) FSUAE_EFFECTIVE_ARGS+=(--uae_ntsc=false) ;;
      --uae_ntsc=true|--uae_ntsc=yes|--uae_ntsc=1) FSUAE_EFFECTIVE_ARGS+=(--ntsc_mode=1) ;;
      --uae_ntsc=false|--uae_ntsc=no|--uae_ntsc=0) FSUAE_EFFECTIVE_ARGS+=(--ntsc_mode=0) ;;
      --cpu=*)
        # FS-UAE compares letters, digits and + only, ignoring case.
        cpu=$(printf '%s' "${arg#*=}" | tr -cd 'A-Za-z0-9+' | tr 'a-z' 'A-Z')
        case "$cpu" in
          AUTO) ;;
          68000|68010|68EC020|68020|68EC030) mmu=0 fpu=0 ;;
          68030) mmu=68030 fpu=0 ;;
          68040) mmu=68040 fpu=68040 ;;
          68060) mmu=68060 fpu=68060 ;;
          68040NOMMU) mmu=0 fpu=68040 ;;
          68060NOMMU) mmu=0 fpu=68060 ;;
          68EC040|68EC060) mmu=0 fpu=0 ;;
          68LC040) mmu=68040 fpu=0 ;;
          68LC060) mmu=68060 fpu=0 ;;
          *)
            echo "Unsupported CPU '${arg#*=}': FS-UAE would run the model's default CPU instead." >&2
            echo "Use 68000, 68010, 68EC020, 68020, 68EC030, 68030, 68EC040, 68LC040, 68040, 68040-NOMMU," >&2
            echo "68EC060, 68LC060, 68060 or 68060-NOMMU. A 68030 without MMU is 68EC030 (no FPU) or" >&2
            echo "--cpu=68030 --uae_mmu_model=0." >&2
            return 1 ;;
        esac ;;
      --jit_compiler=1)
        case "$seen" in *'|--uae_cachesize|'*) ;;
          *) seen="$seen--uae_cachesize|"; FSUAE_EFFECTIVE_ARGS+=(--uae_cachesize=8192) ;;
        esac ;;
      --jit_compiler=0)
        case "$seen" in *'|--uae_cachesize|'*) ;;
          *) seen="$seen--uae_cachesize|"; FSUAE_EFFECTIVE_ARGS+=(--uae_cachesize=0) ;;
        esac ;;
      --uae_cachesize=*)
        case "$seen" in *'|--jit_compiler|'*) ;;
          *) seen="$seen--jit_compiler|"
             if [ "${arg#*=}" = 0 ]; then FSUAE_EFFECTIVE_ARGS+=(--jit_compiler=0)
             else FSUAE_EFFECTIVE_ARGS+=(--jit_compiler=1); fi ;;
        esac ;;
    esac
  done
}

fsuae_validate_options() {
  local arg binary revision
  for arg in "${FSUAE_EFFECTIVE_ARGS[@]}"; do
    [ "$arg" = --jit_compiler=1 ] || continue
    binary=$(command -v "${FSUAE:-fs-uae}") || return 1
    revision="$(dirname "$binary")/source-revision.txt"
    if [ -f "$revision" ] && grep -q 'JIT disabled' "$revision"; then
      echo 'This FS-UAE build has JIT disabled; select a JIT-capable build or remove the JIT override.' >&2
      return 1
    fi
  done
  return 0
}

fsuae_start() {
  fsuae_env "$@"
  exec "${FSUAE:-fs-uae}" "$@"
}

fsuae_command() {
  [ -n "${FSUAE_ARGS+set}" ] || fsuae_options || return 1
  fsuae_setup || return 1
  # shellcheck disable=SC2086
  fsuae_monitor ${EXTRA_ARGS:-} "$@" "${FSUAE_ARGS[@]}" || return 1
  # shellcheck disable=SC2086  # EXTRA_ARGS is word-split on purpose
  fsuae_resolve_options ${EXTRA_ARGS:-} "$FSUAE_GROUP_END" \
    ${FSUAE_MONITOR_ARGS[@]+"${FSUAE_MONITOR_ARGS[@]}"} "$FSUAE_GROUP_END" \
    ${FSUAE_SETUP_ARGS[@]+"${FSUAE_SETUP_ARGS[@]}"} "$FSUAE_GROUP_END" \
    "$@" "$FSUAE_GROUP_END" "${FSUAE_ARGS[@]}" --title="$(fsuae_title)" || return 1
  fsuae_validate_options
}

fsuae_launch() {
  fsuae_command "$@" || return 1
  local log="${FSUAE_LOG:-$FSUAE_RUN/fsuae.log}"
  # The subshell execs, so $! is the emulator itself (what fsuae_stop_previous checks).
  ( fsuae_start "${FSUAE_EFFECTIVE_ARGS[@]}" ) > "$log" 2>&1 &
  fsuae_track $!
  echo "fs-uae pid $FSUAE_PID (log $log, port $DEBUG_PORT)"
}

fsuae_exec() {
  fsuae_command "$@" || return 1
  fsuae_track_self
  fsuae_start "${FSUAE_EFFECTIVE_ARGS[@]}"
}
