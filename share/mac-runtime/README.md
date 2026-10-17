# Shared Macintosh runtime helpers

These sources are canonical, platform-independent services for the Macintosh ports.
`RectBounds.h` is used by Alone in the Dark and Prince of Persia 2. It combines the
rectangle helper and OffsetRect/InsetRect operations from Alone in the Dark.
EqualRect additionally compares all four coordinates without normalizing empty or
inverted bounds; Prince of Persia 2 pairs its Boolean result with System 7.5.5.
Union/intersection accept explicit load/store template arguments, like adjustment.
Native callers can select shared `BigEndianMemory` word accesses while retaining
the same signed comparisons, empty handling and full-input-before-output rule.
The default overloads retain byte accesses; consumers opt in per call.
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
source spans; the 68020 path converts eight longwords per loop with a register
XOR mask, then exact longword/byte tails. Decimated spans retain their byte path.

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

System 7.5.5 fixtures in Prince of Persia 2 and Alone in the Dark establish that
counts decrement modulo 16 bits, and only reaching zero dispatches. A callback
leaving zero is removed; VRemove then returns qErr (-1). AitD's original fixture
also verifies that automatic and explicit removal leave the removed record's
qLink intact. Keep these policies in the consumer adapter; check membership before
reading a returned callback's record, since it may have removed itself. Removing
one callback must adjust the pass iterator without skipping its next neighbour.

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
and sanitizer heap tests cover this contract. Prince of Persia 2 adopts this helper under item 19.7 with its own original
System 7.5.5 placement fixture.

`HeapResize.inc` supplies in-place resizing for the same allocator adapters.
The zone must have no adjacent free blocks on entry. A split or growth can only
create a free/free pair at the resized allocation's tail, so merge that pair
locally instead of rescanning the zone. Logical sizes, allocation placement,
free-byte accounting and the adapter's compaction/failure paths stay unchanged.
Alone in the Dark's sanitizer tests combine resizing with 2,500 fragmented-heap
operations and check that no adjacent free blocks survive. Prince of Persia 2 adopts the same helper under item 19.7.

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

`PenRect8.h` draws a solid zero-displacement QuickDraw pen as a directly clipped
half-open rectangle. It validates map capacity, signed pen extents and all four
clipping bounds before writing. Small spans avoid general rectangle setup;
large spans reuse the aligned fill primitive. The caller supplies a current
allocation capacity; no handle or framebuffer cache is retained by the helper.

`RegionRows::ValidationCache` retains fully validated region encodings in a
32 KiB FIFO byte arena with 32 slots (maximum 4096 bytes per record). Keys include
every byte; capacity checks precede lookup, and arena reuse evicts overlapping
entries. `CopyBits8` validates the whole mask before rejecting a disjoint
rectangle, then clips by coordinates and streams rows. Thumbnail scaling uses
a separate routine; no pixel snapshots or handle-address keys are retained.

`HandleCopy.h` duplicates owned handle data through a heap adapter, protects
the source from purging during allocation and restores its state on success or
failure. The new handle retains its allocator default state. Prince of Persia 2
measures HandToHand against System 7.5.5 and tests this helper with the real heap;
trap-register and error contracts remain the caller's responsibility.

`BitmapRegion.h` converts MSB-first one-bit masks with `RegionOps::Writer`,
using caller-owned staging storage. Region edge storage accommodates thirty-two
transitions, including intermediate XOR states of smaller adjacent rows. Invalid
extents or capacity exhaustion reject before a caller publishes the result.

`HeapLockHandle.inc` consolidates HLock into one validated master-slot lookup,
using the existing query error policy without rewriting unchanged zone headers. It preserves
resource/purge flags and never moves payloads or changes the free list. Consumers
declare `int16_t lockHandle(Handle)` and include the method beside their state
accessors. Prince of Persia 2 checks whole-arena equality against state/setState
composition for all 256 state inputs, plus disposed/null/interior rejection.

`HeapReadHandleState.inc` reads HGetState with one validated master-slot lookup.
It preserves allocated-slot rejection, high state bits, query MemError and the
read-only zone-header policy. Its controls cover all 256 slot-byte values and
null handles; consumers also exercise their real master-block ownership guards.

`PinnedSlotRanges.h` retains sixteen recently validated immutable master-block
ranges behind a caller's last-range fast path. Membership and slot alignment
are checked on every lookup; allocation flags and pointees are never cached.
Call `clear()` whenever the arena resets. It is unsuitable for blocks that can
move, shrink or be freed during an arena's lifetime.

`VideoTicks::deadlinePALBeam` inverts the nominal PAL beam-to-microsecond
conversion for due/not-due checks. It retains the 19,999-microsecond clamp and
requires a stable beam snapshot with HP below 227. Tests cover both sides of
every microsecond boundary and every valid PAL beam position. It changes no
deadline or clock epoch.

`PaulaChannelState.h` factors Alone in the Dark's settled-channel and conservative
period-ceiling bookkeeping out of its hardware wrapper. Reset it at takeover;
mark a channel quiet only after the DMA-off and DAC-zero waits complete. It does
not replace those waits or infer quietness from a zero volume.
After the DMA-off wait, `disabled()` also permits an immediate replacement to
avoid repeating that wait. This is not a quiet DAC: an actual stop still needs
the DAT-zero handshake, as do error cleanup and hardware handoff.

`ImmutablePcmCache.h` generalizes the donor's retained immutable song variants
with bounded memory and explicit users. The caller supplies the plan comparison,
conversion and allocation policies. Every conversion-affecting field belongs in
the comparison; period may be excluded when only sample stride affects bytes.
Sources must remain owned and immutable throughout retention. Stop DMA before
releasing its entry, and release every user before clearing at shutdown. Mutable
effect descriptors/data need a different policy. Exhaustion returns null for an
uncached fallback; it never evicts samples still used by DMA.
`DirtyBands.h` extracts Alone in the Dark’s coordinate-only disjoint C2P planner.
Callers supply viewport dimensions and input capacity; it clips before alignment,
coalesces adjacent equal bands and falls back to a complete bounding rectangle
on output exhaustion. Synthetic controls cover both 320×200 and 512×384 views.
`BlitterCompletion.h` supplies the completion policy for AmigaHardware’s existing
blitter queue. Its hardware adapter is template-injected for latency/race tests.
The platform owns INTB_BLIT, excludes producers while advancing the queue, bounds
the batch to queue capacity, and drains before CPU access, OS handback or teardown.
It acknowledges completion before starting the next blit, including zero-latency
completion; synchronous consumers do not change.
`HeapFindSpace.inc` retains the first-fit allocation policy while skipping a
known occupied prefix. The adapter owns a mutable `searchStart_` block boundary,
initially `headerBytes`. Split rewinds it to the modified block; coalescing records
the first free block or zone end; compaction resets it. MoveHHi must finish through
release/coalesce. The full-heap invariant must reject an interior hint or a free
block preceding it. No fitting-size cache or placement change is permitted.
Prince of Persia 2's mixed-operation oracle compares against a complete chain walk;
the standalone shared test enumerates all small occupancy layouts and safe hints.
