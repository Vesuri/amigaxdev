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

`GWorld8.h`, `CopyBits8.h`, `FillRect8.h`, `WindowGeometry.h`, `RegionRows.h`
and `RegionOps.h` consolidate the existing Alone in the Dark helpers used by
Prince of Persia 2. Define `AMIGAXDEV_REGION_UNION` to add region union to the parity-region
operations. Consumers that do not use it retain the existing operation set and
compiled dispatch; both configurations have sanitizer checks. Trap ownership and
current-port selection remain consumer responsibilities.

`BigEndianMemory.h` shares Alone in the Dark’s explicit 68020 word/longword
accesses, including unaligned addresses and alias-safe memory operands. Its host
fallback preserves big-endian byte order; callers remain responsible for bounds.
The native `AMIGAXDEV_MEMORY_PRIMITIVES_ONLY` mode exposes those same instruction
macros to legacy adapters without adding inline function nodes to their compiler
graph; this preserves Alone in the Dark’s existing function order and executable.

`CodeRangeCache.h` uses a 64-slot page-indexed cache of original CODE ranges. It rechecks
the current base and size on every hit and retains the full search on misses;
callers supply disjoint ranges and retain their own unknown-caller handling.

`PcmDma.inc` shares Alone in the Dark’s signed PCM conversion with Prince of Persia 2.
Include it inside a namespace after defining `Dma` with `layout` and `stride`.
It preserves decimated loop phase and word padding while copying uninterrupted
source spans; the 68020 path converts four ordinary samples per transfer.

`ResourceDirectory.h` and `ResourceDirectory.cpp` share Alone in the Dark's mutable
resource metadata, stable identities and streamed publication. Define
`AMIGAXDEV_RESOURCE_DIRECTORY_INDEXED` consistently across a consumer to enable
Vette-style binary lookup over a lazily rebuilt sorted index. Identity breaks ties
so the oldest surviving duplicate wins even after slot reuse. Successful opens,
closes, additions, replacements and removals invalidate that index. The default
configuration retains the existing linear implementation. Define
`AMIGAXDEV_RESOURCE_DIRECTORY_MAP_LIMIT` to enforce the parser's per-map resource
limit before mutation, as Prince of Persia 2 does.

`VBLPasses.h` factors queued virtual-retrace bookkeeping from Vette! and Alone
in the Dark. Each elapsed Macintosh tick starts a separate queue pass; callbacks
resume the same pass after returning. Consumers retain task records, countdown
semantics, ownership checks and user-mode trampolines. Synthetic tests exercise
tick conservation, task removal, in-flight arrivals and wraparound.

`VideoTicks.h` shares Alone in the Dark's PAL/NTSC field conversion and adds
within-field PAL TickCount calculation. The platform must supply a coherent field
epoch and beam position; callback scheduling and hardware sampling stay outside
the helper. Tests include repeated five-tick deadlines that field-only ticks miss.

`HeapMoveHigh.inc` supplies `MacHeap::moveHigh` for the common arena/master-block
allocator used by Alone in the Dark and Prince of Persia 2. Include it at file
scope after the class declaration; the adapter supplies its existing block layout,
copy helpers, validation and result publication. A fitting free tail before the
next pinned block permits target-only relocation. Interior holes and insufficient
tail space require the original compaction fallback. Payloads, handle flags and
pinned addresses remain intact. Alone in the Dark's original System 7.5.5 fixture
and sanitizer heap tests cover this contract. The owner deferred Prince of Persia 2
adoption while work there is ongoing; keep HEAP.1's size-preserving resize work on
the same shared-allocator path instead of forking placement fixes.

`HeapResize.inc` supplies in-place resizing for the same allocator adapters.
The zone must have no adjacent free blocks on entry. A split or growth can only
create a free/free pair at the resized allocation's tail, so merge that pair
locally instead of rescanning the zone. Logical sizes, allocation placement,
free-byte accounting and the adapter's compaction/failure paths stay unchanged.
Alone in the Dark's sanitizer tests combine resizing with 2,500 fragmented-heap
operations and check that no adjacent free blocks survive. Prince of Persia 2
adoption remains deferred by the owner.

`RegionResultCache.h` retains successful, pure QuickDraw record transformations
in a 32 KiB FIFO arena with 32 metadata slots. The operation tag and exact input
record bytes are the key; callers validate/compute misses and only insert
successful results. Handles and pixel buffers are not cached. It is optional
caller-owned storage, exercised by Alone in the Dark's polygon/InsetRgn camera
mask rebuilding and mutation/relocation/eviction sanitizer fixtures.

`RGBColorCache.h` memoizes successful RGB-to-index lookups per port. Keys include
both dereferenced table addresses, their QuickDraw seeds, format headers and all
48 RGB bits. Relocation, seed or header changes invalidate the entries. The
adapter must also invalidate on port disposal and any same-seed table rebuild;
QuickDraw table edits must publish a new seed. Misses use `GWorld8::colorIndex`,
including its collision-ring validation and first-entry tie rule. This caches
indices, never pixels, and requires no allocation or per-call table copy.
