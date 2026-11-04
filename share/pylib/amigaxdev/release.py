"""Deterministic Amiga release archives (LH5, level-0 headers) and installer icons.

A port's tools/package_release.py keeps only its own file map:

    from amigaxdev import release
    icons = ROOT / 'release/icons'
    files = {'Game': exe, 'Game.slave': slave, 'Game.inf': release.installer_icon(icons, 'Game', game=True),
             'Install': ..., 'Install.info': release.installer_icon(icons, 'Game'), ...}
    release.refuse_originals(files, ORIGINAL_HASHES)
    data = release.archive('Game Install', files, release.template_icon(icons, 'drawer.info.b64'),
                           release.dos_stamp(2026, 10, 11))
    release.write(out / f'Game-{version}.lha', data, refuse_overwrite=True)

The members come in sorted name order after the drawer icon, each with the given DOS date, MS-DOS
attribute 0x20 and backslash paths, so the same inputs and stamp give the same bytes on any host.
LHa for UNIX does the compression (`$LHA`, else `lha-compress` on PATH, else the shared build);
Lhasa cannot create archives.
"""
import base64
import hashlib
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from .env import path as env_path


def dos_stamp(year, month, day):
    """The 32-bit DOS date/time field for midnight of the given day."""
    return (((year - 1980) << 9) | (month << 5) | day) << 16


def crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc


def encoder():
    return os.environ.get('LHA') or shutil.which('lha-compress') or env_path('LHA')


def member(name, data, stamp):
    # Use the established UNIX LHa encoder, but own the generic header so host
    # timestamps, permissions and paths cannot affect release reproducibility.
    with tempfile.TemporaryDirectory(prefix='amigaxdev-lh5-') as directory:
        work = Path(directory)
        (work / 'payload').write_bytes(data)
        try:
            subprocess.run([encoder(), 'ao5g0', 'member.lha', 'payload'],
                           cwd=work, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as error:
            raise SystemExit('LH5 packaging requires LHa for UNIX (not Lhasa); '
                             'set LHA to its absolute path') from error
        raw = (work / 'member.lha').read_bytes()
    header = raw[2:2 + raw[0]]
    if header[:5] not in (b'-lh5-', b'-lh0-') or header[18] != 0:
        raise ValueError('compressor did not produce a level-zero LH5/LH0 member')
    packed, unpacked = struct.unpack_from('<II', header, 5)
    payload = raw[2 + raw[0]:2 + raw[0] + packed]
    if unpacked != len(data) or len(payload) != packed:
        raise ValueError('invalid compressor output lengths')
    name = name.replace('/', '\\').encode('ascii')
    # LHa stores incompressible small members; retain that declared method.
    body = header[:5] + struct.pack('<III', len(payload), len(data), stamp)
    body += bytes((0x20, 0, len(name))) + name + struct.pack('<H', crc16(data))
    return bytes((len(body), sum(body) & 255)) + body + payload


def check_names(names, *, component_limit=30, encoding='ascii'):
    """Validate extracted or planned member names for the selected target filesystem.

    The default is the classic Amiga 30-byte component limit. Include .info in
    the length; do not silently truncate or rename. Archive output is ASCII.
    Pass actual independently extracted names again during release validation.
    """
    if not isinstance(component_limit, int) or component_limit < 1:
        raise ValueError('component_limit must be positive')
    seen = set()
    for name in names:
        if not isinstance(name, str) or not name or '\\' in name or ':' in name:
            raise ValueError(f'invalid archive path: {name!r}')
        for part in name.split('/'):
            if part in ('', '.', '..') or any(ord(c) < 32 or ord(c) == 127 for c in part):
                raise ValueError(f'invalid archive component: {name!r}')
            if len(part.encode(encoding)) > component_limit:
                raise ValueError(f'filename exceeds {component_limit} bytes: {name}')
        folded = name.casefold()
        if folded in seen:
            raise ValueError(f'case-insensitive duplicate member: {name}')
        seen.add(folded)


def check_extracted_names(directory, expected, *, component_limit=30):
    """Check independently extracted files, exact names and expected icon pairing.

    ``expected`` is the complete planned file list, including drawer .info files.
    Exact equality detects truncation, missing icons and unexpected members.
    """
    expected = list(expected)
    check_names(expected, component_limit=component_limit)
    root = Path(directory)
    actual = []
    directories = []
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('release contains a symlink: ' + str(path.relative_to(root)))
        if path.is_file():
            actual.append(path.relative_to(root).as_posix())
        elif path.is_dir():
            directories.append(path.relative_to(root).as_posix())
    check_names(actual, component_limit=component_limit)
    check_names(directories, component_limit=component_limit)
    expected_directories = {str(parent) for name in expected for parent in Path(name).parents
                            if str(parent) != '.'}
    if set(directories) != expected_directories:
        raise ValueError('extracted directory names differ from planned members')
    if set(actual) != set(expected):
        raise ValueError(f'extracted members differ: missing={set(expected)-set(actual)}, '
                         f'unexpected={set(actual)-set(expected)}')


def archive(prefix, files, drawer_icon, stamp, *, component_limit=30):
    """`prefix.info` (the drawer icon), then `prefix/NAME` for each file in name order, then the
    archive's end byte."""
    check_names([prefix + '.info'] + [prefix + '/' + name for name in files],
                component_limit=component_limit)
    return (member(prefix + '.info', drawer_icon, stamp)
            + b''.join(member(prefix + '/' + name, data, stamp)
                       for name, data in sorted(files.items())) + b'\0')


def refuse_originals(files, original_hashes):
    """Stop if any file is byte-identical to a known original (sha256 hex digests)."""
    for name, data in files.items():
        if hashlib.sha256(data).hexdigest() in original_hashes:
            raise SystemExit('refusing to package original game data: ' + name)


def audit_executable(elf, packaged, convert, *, diagnostic_patterns, runtime_symbols,
                     verification=False, objdump='m68k-amiga-elf-objdump'):
    """Audit symbols and bind that audit to the executable actually extracted.

    ``convert(Path(elf))`` must run the project's deterministic ELF-to-HUNK
    conversion and return bytes. ``packaged`` is the extracted executable path.
    Patterns are full-match regexes naming expensive diagnostic code/data; each
    must match in a verification build and none may match in release. Required
    runtime guard symbols must remain in both. Also run behavioral rejection
    tests: symbol presence alone does not establish that a guard works.
    """
    if not diagnostic_patterns or not runtime_symbols:
        raise ValueError('explicit diagnostic and runtime guard policies are required')
    table = subprocess.check_output([objdump, '-t', str(elf)], text=True)
    names = {line.split()[-1] for line in table.splitlines()
             if len(line.split()) >= 6 and '*UND*' not in line}
    missing = set(runtime_symbols) - names
    if missing:
        raise ValueError('missing runtime guards: ' + ', '.join(sorted(missing)))
    for pattern in diagnostic_patterns:
        found = {name for name in names if re.fullmatch(pattern, name)}
        if bool(found) != verification:
            raise ValueError(f'diagnostic policy failed: {pattern}: {sorted(found)}')
    rebuilt = convert(Path(elf))
    if not isinstance(rebuilt, bytes) or not rebuilt.startswith(b'\0\0\x03\xf3'):
        raise ValueError('converter must return a HUNK executable')
    actual = Path(packaged).read_bytes()
    if actual != rebuilt:
        raise ValueError('packaged executable differs from the audited ELF conversion')
    return hashlib.sha256(actual).hexdigest()


def write(archive_path, data, refuse_overwrite=False):
    """Write through a .part file, so a failed run never leaves a half archive."""
    archive_path = Path(archive_path)
    if refuse_overwrite and archive_path.exists():
        raise SystemExit('Refusing to replace an existing release archive: ' + str(archive_path))
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_suffix('.lha.part')
    temporary.write_bytes(data)
    temporary.replace(archive_path)
    return archive_path


# --- icons -------------------------------------------------------------------------------------
# A project keeps its template icons base64 in release/icons/: drawer.info.b64,
# readme.info.b64, install.info.b64 (Installer's tool types) and game.inf.b64 (distributed as
# <Game>.inf, renamed and configured by Installer).


def template_icon(icons_dir, name):
    return base64.b64decode((Path(icons_dir) / name).read_bytes())


def installer_icon(icons_dir, appname, game=False, require=()):
    """Install.info with APPNAME set to appname, or the game icon unchanged (game=True).
    `require` lists byte strings the template must contain (e.g. b'MINUSER=AVERAGE\\0')."""
    if game:
        return template_icon(icons_dir, 'game.inf.b64')
    data = template_icon(icons_dir, 'install.info.b64')
    for r in require:
        assert r in data, r
    new = b'APPNAME=' + (appname.encode('latin-1') if isinstance(appname, str) else appname) + b'\0'
    # the template's one APPNAME tool type: a big-endian length, then the NUL-terminated string
    assert data.count(b'APPNAME=') == 1
    start = data.index(b'APPNAME=')
    assert start >= 4
    length = struct.unpack('>I', data[start - 4:start])[0]
    assert data[start + length - 1:start + length] == b'\0'
    return data[:start - 4] + struct.pack('>I', len(new)) + new + data[start + length:]
