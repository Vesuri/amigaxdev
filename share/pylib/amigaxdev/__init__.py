"""Shared Python tools for the Amiga projects, installed by AmigaXDev into
~/.local/share/amiga/pylib (on the shared venv's path through amigaxdev.pth).

A project tool that may run under another python3 finds it with the three-line shim in
AmigaXDev docs/environment.md.  Modules:

  env       shared paths with environment overrides: path(), tool()
  barto     FS-UAE/Barto `monitor profile` trace reader
  gdbserve  drive a game in FS-UAE through the gdb stub: a per-project command server
  disasm    objdump over memory dumps (dis, disd and hotspots commands)
  adf       list and extract files from an OFS/FFS floppy image
  patchlist decode a WHDLoad resload_Patch list inside a slave
  release   deterministic LH5 release archives and installer icons
  mac       Macintosh originals: MacBinary, resource forks, HFS, A-trap names, 68k sweep
  dos       DOS originals: MZ headers, the Amiga runtime check
  framework the canonical dA JoRMaS framework: diff and sync against a port's copy
"""
