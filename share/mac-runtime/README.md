# Shared Macintosh runtime helpers

These sources are canonical, platform-independent services for the Macintosh ports.
`RectBounds.h` is used by Alone in the Dark and Prince of Persia 2. It combines the
rectangle helper and OffsetRect/InsetRect operations from Alone in the Dark.
`BitmapFont.h` shares the existing compatibility-font parser and a bounded reader
for original one-bit FOND/NFNT resources. `BitmapText8.h` adapts the clipping and
pixel addressing of Alone in the Dark’s Text8 renderer to NFNT glyphs with integer
advances and bearings; it contains no game-specific font tables.

`make share` installs this directory under `$AMIGA_SHARE/mac-runtime`. Consumers
vendor byte-identical files under `src/mac/` and pin them in
`manifest/shared-runtime.sha256`. Build and host-test entry points verify those pins.
Change the canonical source, install it, then update clean consumers together and
validate their callers. Do not maintain independent per-game implementations.
Installed edits must return through `make pull-shared` before installation.

Run `make test-mac-runtime` for the portable synthetic edge and alias checks.
