# Open work

## Shared debugger keyboard and mouse input

Provide and document a common way for game harnesses to send keyboard, mouse
and joystick input through the emulator debugger. The current playbooks discuss
failed posted host key events and project-specific input tapes, but do not explain
the debugger-native input extensions already used by sibling projects.

Reference implementations: 4D Sports Driving uses `monitor key` (Amiga raw key
press/release) and `monitor fields`; Ferrari Formula One uses `monitor mouse`
and `monitor input`. These are extensions in private emulator builds, not
commands that can be assumed available in the installed shared build.

- Review and consolidate the extensions into a pinned shared diagnostic build;
  expose capability checks and fail clearly when a command is unavailable.
- Document raw key codes, press/release and held-key combinations, relative mouse
  motion, button/joystick events, bounded field advancement, and input cleanup.
- Provide reusable harness helpers and examples that verify actual guest input
  and resulting game state, with action logs suitable for repeatable runs.
- Keep input on the emulator's native input path. Do not require Mac accessibility,
  host-window focus, posted host events or direct writes to game control state.
- Document profiler compatibility and timing limits of each supported build;
  distinguish gameplay coverage from deterministic performance benchmarks.
- Update the playbooks and headless FS-UAE reference so new game projects can
  discover this route before inventing another local helper.

Acceptance: keyboard press/hold/release and mouse motion/button smoke tests run
through the shared debugger interface without host accessibility; an unsupported
build gives an actionable error; the documented examples work in a game harness.
