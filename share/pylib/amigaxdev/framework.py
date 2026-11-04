"""The canonical framework ($AMIGA_FRAMEWORK) against a port's vendored copy.

  python3 -m amigaxdev.framework diff PROJECT [--template DIR]
      one line per file: identical, local change, upstream change missing, diverged, or only
      on one side; numbers are changed lines after prefix normalisation
  python3 -m amigaxdev.framework diff PROJECT FILE
      the unified diff of one file (canonical -> port)
  python3 -m amigaxdev.framework sync PROJECT FILE...
      copy canonical files into the port, renamed to the port's prefixes (review the result with
      the port's own build and measurements before committing)

PROJECT is the port's checkout (or its framework directory).  Ports rename the framework's
identifiers when they vendor it (GAME_SASC_ALIAS, game_mulu16, ...); both sides are compared
with those prefixes mapped to DAJ_/daj_ and the 16-bit math header include mapped to
"daj_math.h".  With a template directory (--template, or $DAJ_TEMPLATE: the copy both
sides started from), a file that differs is classified by which side still matches the template.
"""
import difflib
import os
import re
import sys
from pathlib import Path

from .env import path as env_path

SOURCE = re.compile(r'.*\.(cpp|h|s)$')
MATH_INCLUDE = re.compile(r'#include "(?:\.\./)*(?:cpu/)?(?:m68k_math|daj_math)\.h"')


def framework_dir(project):
    p = Path(project)
    for candidate in (p / 'src/platform/amiga/framework', p):
        if (candidate / 'AmigaHardware.h').exists():
            return candidate
    raise SystemExit(f'no framework (AmigaHardware.h) under {project}')


def prefixes(directory):
    """(MACRO_PREFIX, func_prefix, math include line) a port uses, from its own files."""
    text = ''.join(f.read_text(errors='replace') for f in directory.iterdir()
                   if SOURCE.match(f.name))
    macro = re.search(r'\b([A-Za-z0-9]+)_SASC_ALIAS\b', text)
    func = re.search(r'\b([A-Za-z0-9]+)_mul[su]16\b', text)
    inc = MATH_INCLUDE.search(text)
    return (macro.group(1) if macro else None, func.group(1) if func else None,
            inc.group(0) if inc else None)


def normalise(text, pre):
    macro, func, inc = pre
    if macro and macro != 'DAJ':
        text = re.sub(rf'\b{macro}_', 'DAJ_', text)
    if func and func != 'daj':
        text = re.sub(rf'\b{func}_(mul|div|mod)', r'daj_\1', text)
    return MATH_INCLUDE.sub('#include "daj_math.h"', text)


def denormalise(text, pre):
    macro, func, inc = pre
    if macro:
        text = re.sub(r'\bDAJ_', f'{macro}_', text)
    if func:
        text = re.sub(r'\bdaj_(mul|div|mod)', rf'{func}_\1', text)
    if inc:
        text = text.replace('#include "daj_math.h"', inc)
    return text


def files(directory):
    return {f.name for f in directory.iterdir() if f.is_file() and SOURCE.match(f.name)}


def changed(a, b):
    return sum(1 for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm='', n=0)
               if l[:1] in '+-' and l[:3] not in ('+++', '---'))


def report(project, template=None):
    port, canon = framework_dir(project), Path(env_path('AMIGA_FRAMEWORK'))
    ppre, cpre = prefixes(port), prefixes(canon)
    tdir = Path(template) if template else None
    tpre = prefixes(tdir) if tdir else None
    print(f'{port}: prefixes ' + (f'{ppre[0] or "-"}_ / {ppre[1] or "-"}_'
                                   if ppre[0] or ppre[1] else 'none (no prefixed macros or math helpers)'))
    for name in sorted(files(port) | files(canon)):
        if name not in files(canon):
            print(f'  port only           {name}')
            continue
        if name not in files(port):
            print(f'  canonical only      {name}')
            continue
        p = normalise((port / name).read_text(errors='replace'), ppre)
        c = normalise((canon / name).read_text(errors='replace'), cpre)
        if p == c:
            print(f'  identical           {name}')
            continue
        kind = 'differs'
        if tdir and (tdir / name).exists():
            t = normalise((tdir / name).read_text(errors='replace'), tpre)
            kind = ('upstream change missing' if p == t else
                    'local change' if c == t else 'diverged')
        print(f'  {kind:<19} {name} ({changed(c, p)} lines)')


def show(project, name):
    port, canon = framework_dir(project), Path(env_path('AMIGA_FRAMEWORK'))
    c = normalise((canon / name).read_text(errors='replace'), prefixes(canon)).splitlines()
    p = normalise((port / name).read_text(errors='replace'), prefixes(port)).splitlines()
    for l in difflib.unified_diff(c, p, f'canonical/{name}', f'port/{name}', lineterm=''):
        print(l)


def sync(project, names):
    port, canon = framework_dir(project), Path(env_path('AMIGA_FRAMEWORK'))
    ppre, cpre = prefixes(port), prefixes(canon)
    for name in names:
        text = normalise((canon / name).read_text(), cpre)
        (port / name).write_text(denormalise(text, ppre))
        print(f'synced {port / name}')


def main(argv):
    if len(argv) < 2 or argv[0] not in ('diff', 'sync'):
        sys.exit(__doc__)
    cmd, project, rest = argv[0], argv[1], argv[2:]
    template = os.environ.get('DAJ_TEMPLATE') or None
    if '--template' in rest:
        i = rest.index('--template')
        template = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    if cmd == 'diff':
        show(project, rest[0]) if rest else report(project, template)
    else:
        sync(project, rest)


if __name__ == '__main__':
    main(sys.argv[1:])
