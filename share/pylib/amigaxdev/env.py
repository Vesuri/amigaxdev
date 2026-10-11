"""Shared Amiga paths with environment overrides: the defaults of the shared env.sh.

    from amigaxdev.env import path, tool
    path('KICKSTART13')          # $KICKSTART13, else the shared default
    tool('objdump')              # $AMIGA_TOOLCHAIN/bin/m68k-amiga-elf-objdump
"""
import os

_PREFIX = '~/.local'
_SHARE = '~/.local/share/amiga'

DEFAULTS = {
    'AMIGA_PREFIX': _PREFIX,
    'AMIGA_SHARE': _SHARE,
    'AMIGA_TOOLCHAIN': _PREFIX + '/opt',
    'VASM': _PREFIX + '/vasmm68k_mot',
    'NDK': _PREFIX + '/opt/m68k-amiga-elf/sys-include',
    'FSUAE_ARM': _SHARE + '/fs-uae-arm/fs-uae',
    'FSUAE_APROF': _SHARE + '/fs-uae-aprof/fs-uae',
    'AMIGA_UNICORN': _SHARE + '/unicorn',
    'KICKSTART': _SHARE + '/Kickstarts/kick40063.A600',
    'KICKSTART_A1200': _SHARE + '/Kickstarts/kick40068.A1200',
    'KICK13': _SHARE + '/Kickstarts/kick34005.A500',
    'KICKSTART13': _SHARE + '/Kickstarts/kick34005.A500',
    'RTB': _SHARE + '/Kickstarts/kick34005.A500.RTB',
    'WORKBENCH_ADF': _SHARE + '/Workbenchv2.04rev37.67Workbench.adf',
    'SETPATCH': _SHARE + '/SetPatch',
    'WHDLOAD': _SHARE + '/WHDLoad-20.0',
    'WHDLOAD_BINARY': _SHARE + '/WHDLoad-20.0/C/WHDLoad',
    'INSTALLER43': _SHARE + '/Installer43/Installer',
    'ADCD': _SHARE + '/adcd21/Reference',
    'AGA_GUIDE': _SHARE + '/AGA.Guide',
    'FSUAE_COMMON': _SHARE + '/fsuae_common.sh',
    'LHA': _SHARE + '/lha-compressor/src/lha',
    'AMIGA_PYLIB': _SHARE + '/pylib',
    'AMIGA_GHIDRA_SCRIPTS': _SHARE + '/ghidra_scripts',
    'AMIGA_FRAMEWORK': _SHARE + '/framework',
}


def path(name):
    """$name if set and non-empty, else the shared default (KeyError for unknown names)."""
    return os.environ.get(name) or os.path.expanduser(DEFAULTS[name])


def tool(name):
    """A m68k-amiga-elf binary from AMIGA_TOOLCHAIN, e.g. tool('objdump')."""
    return os.path.join(path('AMIGA_TOOLCHAIN'), 'bin', f'm68k-amiga-elf-{name}')
