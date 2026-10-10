#!/usr/bin/env python3
"""Make every file under SRC present and identical under DEST.

    sync_tree.py SRC DEST REPLACED PREFIX

A file in DEST that differs from SRC is moved to REPLACED/<its path below PREFIX> before the new
one is copied; nothing is deleted.  Files and directories only in DEST are listed and left alone.
Executable bits SRC has are added to identical files in DEST (none are removed). Empty
directories in SRC are created.  Prints a one-line summary.
"""
import filecmp, os, shutil, sys

src, dest, replaced, prefix = sys.argv[1:5]
copied = kept = 0
for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src)
    droot = os.path.normpath(os.path.join(dest, rel))
    os.makedirs(droot, exist_ok=True)
    for f in files:
        s, d = os.path.join(root, f), os.path.join(droot, f)
        if os.path.isfile(d) and not os.path.islink(d) and filecmp.cmp(s, d, shallow=False):
            # Same bytes: only add executable bits the source has (never take any away).
            have, want = os.stat(d).st_mode & 0o777, os.stat(s).st_mode & 0o111
            if want & ~have:
                os.chmod(d, have | want)
            kept += 1
            continue
        if os.path.lexists(d):
            aside = os.path.join(replaced, os.path.relpath(d, prefix))
            os.makedirs(os.path.dirname(aside), exist_ok=True)
            shutil.move(d, aside)
            print(f'setup: WARNING: replaced {d} (the old one is in {aside})', file=sys.stderr)
        shutil.copy2(s, d)
        copied += 1

extra = []
for root, dirs, files in os.walk(dest):
    rel = os.path.relpath(root, dest)
    if not os.path.isdir(os.path.join(src, rel)):
        extra.append(rel + '/')
        dirs[:] = []
        continue
    extra += [os.path.join(rel, f) for f in files if not os.path.lexists(os.path.join(src, rel, f))]
for e in extra:
    print(f'setup: note: {os.path.join(dest, e)} is not part of the installed set', file=sys.stderr)
print(f'setup: {dest}: {copied} copied, {kept} already current'
      + (f', {len(extra)} extra left in place' if extra else ''))
